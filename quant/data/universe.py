# -*- coding: utf-8 -*-
"""全市场异动池（东财 clist）—— 形态模块候选池的"放量·未涨停"补充源。

为什么需要它
------------
修复前形态候选池 = 当日涨停 ∪ 核心池，而**核心池 ⊆ 涨停池**（实测 cores(7) == 连板池(7)
⊆ 涨停池(40)），∪ 是空操作 ⇒ 所有"突破"必然是当日涨停股，形态退化为"涨停股二次筛选器"，
丧失**在涨停之前发现突破**的能力（这正是粘合突破的全部价值）。

现在补一个第三源：从东财全市场列表筛出**当日上涨、放量/活跃、但尚未涨停**的票，
与涨停池、核心池合并去重。这样形态才有机会在"启动第一天"（还没封板）就抓到。

数据源
------
东财 ``push2.eastmoney.com/api/qt/clist/get``（``push2delay`` 同样可用）。
- 全市场约 5913 只，``pz`` **单页上限 100**（传 1000 也只回 100）→ 不能一次拉全。
- 但支持**服务端排序**（``fid``），故按"量比 desc"与"涨幅 desc"各翻几页取头部，
  再本地按阈值过滤 —— 5 次请求即可覆盖"当日最活跃/最强势"的那部分，成本可控。

字段：``f12`` 代码 / ``f14`` 名称 / ``f3`` 涨跌幅% / ``f8`` 换手% / ``f10`` 量比 /
``f6`` 成交额(元) / ``f100`` 行业。

口径（2026-09-11 定）
--------------------
入选（全部满足）：
- 名称不以 ``N`` / ``C`` 开头（新股无形态历史）、不含"退"
- 涨幅 ≥ ``MIN_PCT``(1.0%) 且 **未涨停**（< 该板块涨停幅度 − 0.8pp；ST 按 5cm 计）
- 成交额 ≥ ``AMOUNT_MIN``(1 亿，流动性下限)
- 量比 ≥ ``VOL_MIN``(1.2) **或** 换手 ≥ ``TURN_MIN``(3.0%)

排序取"量比 desc"，截断 ``EXTRA_MAX``(150)。

本模块会被 CloudBase Python3.7 云函数直接引用，故启用
``from __future__ import annotations`` 以兼容 PEP604 写法（X | None）。
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from quant.data.kline import _http, board_limit, normalize_code

EM_UT = "bd1d9ddb04089700cf9c27f6f7426281"
_HOSTS = (
    "https://push2.eastmoney.com",
    "https://push2delay.eastmoney.com",
)
# 全部 A 股：深主板 t:6 / 创业板 t:80 / 沪主板 t:2 / 科创板 t:23 / 北交所 t:81+s:2048
_FS_ALL = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
_FIELDS = "f12,f14,f2,f3,f8,f10,f6,f100"

_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/center/gridlist.html",
}

# ---- 口径常量（调参只改这里） ----
MIN_PCT = 1.0          # 当日涨幅下限 %（突破是上涨事件，不选下跌票）
VOL_MIN = 1.2          # 量比下限
TURN_MIN = 3.0         # 换手下限 %
AMOUNT_MIN = 1e8       # 成交额下限（元）
EXTRA_MAX = 150        # 异动池封顶（控制 K线/资金流 请求量，守住云函数超时）
LIMIT_GAP = 0.8        # 距涨停 ≥ 该 pp 才算"未涨停"（避开 9.9x 这类准板）
_PAGE_SIZE = 100       # clist 单页硬上限
_SORTS = (("f10", 3), ("f3", 2))   # (排序字段, 页数)：量比 desc 3 页 + 涨幅 desc 2 页
# 最近一次全市场取数的诊断（供 pool_meta 透出；部分页失败是本模块最主要的故障模式）
LAST_FETCH: dict = {}


def _num(v, default=None):
    """东财缺失值用 '-' 表示；统一转 float，失败给 default。"""
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v))
    except (TypeError, ValueError):
        return default


def _page(host: str, fid: str, pn: int, pz: int = _PAGE_SIZE):
    """取一页；返回 (rows, total)。失败返回 ([], 0)。"""
    url = (host + "/api/qt/clist/get"
           + "?pn=%d&pz=%d&po=1&np=1&ut=%s&fltt=2&invt=2" % (pn, pz, EM_UT)
           + "&fid=" + fid
           + "&fs=" + _FS_ALL
           + "&fields=" + _FIELDS)
    try:
        raw = _http(url, timeout=15, headers=_UA)
        data = (json.loads(raw).get("data") or {})
    except Exception:
        return [], 0
    diff = data.get("diff")
    if isinstance(diff, dict):          # 部分版本 np=1 时返回 dict
        diff = list(diff.values())
    return (diff or []), int(data.get("total") or 0)


def _jobs(sorts=_SORTS):
    """展开成 [(fid, pn), ...] 待抓页清单。"""
    out = []
    for fid, pages in sorts:
        for pn in range(1, int(pages) + 1):
            out.append((fid, pn))
    return out


def fetch_raw_universe(sorts=_SORTS, hosts=_HOSTS) -> list[dict]:
    """按多种排序翻页抓取原始行（主机兜底 + 并发翻页 + 去重）。

    两个必须的鲁棒性设计（都踩过）：
    1. **并发**：5 页串行实测 ≈5.5s（每页 ~1.1s 往返），并发后 ≈1.2s。
    2. **逐页兜底**：云端实测会出现"部分页成功、部分页失败"（`push2` 不稳定），
       早期版本只要**有任何**一页成功就 `break` 掉备用主机 ⇒ 云端异动池只捞到 34 只
       （本地 150）。现改为**只把失败的那几页**交给下一台主机重试，并合并所有成功页。

    诊断信息写入模块级 ``LAST_FETCH``（供 ``build_pattern_pool`` 透出到前端）。
    """
    global LAST_FETCH
    jobs = _jobs(sorts)
    pending = list(jobs)
    rows, seen = [], set()
    pages_ok, used = 0, []
    for host in hosts:
        if not pending:
            break
        with ThreadPoolExecutor(max_workers=max(1, len(pending))) as ex:
            chunks = list(ex.map(lambda j: (j, _page(host, j[0], j[1])), pending))
        still, got = [], 0
        for j, (chunk, _total) in chunks:
            if not chunk:
                still.append(j)
                continue
            got += 1
            for r in chunk:
                c = str(r.get("f12") or "").strip()
                if c and c not in seen:
                    seen.add(c)
                    rows.append(r)
        if got:
            pages_ok += got
            used.append("%s:%d/%d" % (host.split("//")[1].split(".")[0], got, len(chunks)))
        if got == 0:
            continue              # 本主机整批失败 → 全部留给下一台
        pending = still
    LAST_FETCH = {"jobs": len(jobs), "pages_ok": pages_ok,
                  "pages_fail": len(pending), "raw_rows": len(rows),
                  "hosts": used}
    return rows


def _pick(row: dict):
    """原始行 → 归一化候选；不符合口径返回 None。"""
    raw = str(row.get("f12") or "").strip()
    if not raw:
        return None
    name = str(row.get("f14") or "").strip()
    # 新股（N/C 开头）无形态历史；退市股不参与
    if name[:1] in ("N", "C", "n", "c") or "退" in name:
        return None
    # 深/沪 B 股不参与
    if raw.startswith(("200", "900")):
        return None
    code = normalize_code(raw)
    if not code:
        return None

    pct = _num(row.get("f3"))
    if pct is None or pct < MIN_PCT:
        return None
    lim = board_limit(code, name) * 100.0        # 该板块涨停幅度（ST=5 / 主板=10 / 双创=20 / 北交所=30）
    if pct >= lim - LIMIT_GAP:                   # 已涨停 → 涨停池已覆盖，避免重复
        return None
    amount = _num(row.get("f6"), 0.0) or 0.0
    if amount < AMOUNT_MIN:
        return None
    vol_ratio = _num(row.get("f10"))
    turnover = _num(row.get("f8"))
    if not ((vol_ratio is not None and vol_ratio >= VOL_MIN)
            or (turnover is not None and turnover >= TURN_MIN)):
        return None
    return {
        "code": code,
        "name": name,
        "pct": round(pct / 100.0, 4),            # 与涨停池一致：小数
        "vol_ratio": round(vol_ratio, 2) if vol_ratio is not None else None,
        "turnover": round(turnover / 100.0, 4) if turnover is not None else None,
        "amount": amount,
        "industry": str(row.get("f100") or "").strip(),
    }


def fetch_active_pool(max_n: int = EXTRA_MAX, sorts=_SORTS) -> list[dict]:
    """全市场"放量·未涨停·上涨"异动池，按量比 desc 截断至 max_n。"""
    rows = fetch_raw_universe(sorts=sorts)
    out, seen = [], set()
    for r in rows:
        it = _pick(r)
        if not it or it["code"] in seen:
            continue
        seen.add(it["code"])
        out.append(it)
    out.sort(key=lambda x: (-(x.get("vol_ratio") or 0), -(x.get("amount") or 0)))
    return out[:int(max_n)]


# ---------------------------------------------------------------- 候选池组装（两个调用方共用）

def build_pattern_pool(zt_rows=None, core_rows=None, with_extra: bool = True,
                       extra_max: int = EXTRA_MAX):
    """组装形态候选池：**涨停池 ∪ 核心池 ∪ 全市场异动池**。

    返回 ``(items, pool_meta)``；``items`` 元素形如
    ``{code, name, board, in_core, pool}``，``pool`` ∈ ``zt`` / ``core`` / ``active``。

    ``pool_meta`` 供前端与排障用，含三源计数与异动池口径。
    """
    cmap: dict[str, dict] = {}

    for x in (zt_rows or []):
        c = normalize_code(str(x.get("code") or ""))
        if not c:
            continue
        cmap[c] = {"code": c, "name": x.get("name") or "",
                   "board": int(x.get("board_cnt") or 1),
                   "in_core": False, "pool": "zt"}

    for x in (core_rows or []):
        c = normalize_code(str(x.get("code") or ""))
        if not c:
            continue
        if c in cmap:                       # 已涨停 → 只标核心，不新建
            cmap[c]["in_core"] = True
            continue
        cmap[c] = {"code": c, "name": x.get("name") or "",
                   "board": int(x.get("board") or 0),
                   "in_core": True, "pool": "core"}

    zt_n, core_only_n = 0, 0
    for v in cmap.values():
        if v["pool"] == "zt":
            zt_n += 1
        elif v["pool"] == "core":
            core_only_n += 1

    extra, extra_err = [], None
    if with_extra:
        try:
            extra = fetch_active_pool(max_n=extra_max)
        except Exception as e:
            extra_err = "%s: %s" % (type(e).__name__, e)

    extra_new = 0
    for x in extra:
        c = x["code"]
        if c in cmap:
            continue
        cmap[c] = {"code": c, "name": x.get("name") or "", "board": 0,
                   "in_core": False, "pool": "active"}
        extra_new += 1

    meta = {
        "zt_n": zt_n,                       # 涨停池
        "core_n": core_only_n,              # 核心池中不在涨停池的部分
        "active_n": extra_new,              # 异动池新增（去重后）
        "active_fetched": len(extra),       # 异动池过滤后总数（截断前）
        "total_n": len(cmap),
        "criteria": {
            "min_pct": MIN_PCT, "vol_min": VOL_MIN, "turn_min": TURN_MIN,
            "amount_min": AMOUNT_MIN, "extra_max": int(extra_max),
        },
        "only_zt_effective": extra_new == 0,   # True 表示池子仍退化为"仅涨停池"
        "fetch": dict(LAST_FETCH),             # 全市场取数诊断（页成功/失败、主机）
        "error": extra_err,
    }
    return list(cmap.values()), meta


if __name__ == "__main__":
    rows = fetch_raw_universe()
    picked = fetch_active_pool()
    print("原始行 %d → 异动池 %d" % (len(rows), len(picked)))
    for x in picked[:10]:
        print("  %s %-8s 涨幅%.2f%% 量比%s 换手%s 成交%.2f亿 %s"
              % (x["code"], x["name"], x["pct"] * 100, x["vol_ratio"],
                 (x["turnover"] or 0) * 100, (x["amount"] or 0) / 1e8, x["industry"]))
