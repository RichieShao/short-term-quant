# -*- coding: utf-8 -*-
"""股东性质分类（资金性质「底色」）—— 对应十类资金画像。

背景
----
`quant/data/moneyflow.py` 只有**盘口单量**维度（主力/超大/大/中/小单），回答的是
"今天有多少钱进"，回答不了"**是谁的钱**"。本模块补上后者：把十大流通股东按
资金性质分类，得出每只票的"底色"。

十类映射（数据源：东财 F10 股东研究 `ShareholderResearch/PageAjax`）
--------------------------------------------------------------
======================  ==========================================================
公募基金                ``HOLDER_TYPE`` ∈ {证券投资基金, 基金资产管理计划}（``jjcg`` 另给 50 只明细）
北向资金                名称 == ``香港中央结算有限公司``（⚠ 见下"H 股陷阱"）
QFII / RQFII            ``HOLDER_TYPE == QFII`` 或名称命中境外机构关键词
社保基金                ``HOLDER_TYPE == 全国社保基金``
险资                    ``HOLDER_TYPE`` ∈ {保险产品, 保险公司} 或名称含保险关键词
私募                    ``HOLDER_TYPE == 私募基金``
游资                    ⚠ **季报拿不到** —— 由龙虎榜营业部席位在 T+0 层面补充（见 ma_pattern）
产业资本                实控人 ``sjkzr`` / 员工持股计划 / 前三大股东里的集团·控股·投资类
国家队                  名称含 中央汇金 / 中国证券金融 / 汇金资产 / 国新投资 等
牛散                    ``HOLDER_TYPE == 个人``
======================  ==========================================================

⚠ H 股陷阱（2026-09-12 实测，必须精确匹配）
    A+H 公司的十大流通股东里同时出现：
      ``香港中央结算有限公司``        → 沪/深股通（**北向**）
      ``香港中央结算(代理人)有限公司`` → 港交所代名义持有（**H 股**，不是北向）
      ``HKSCC NOMINEES LIMITED``      → 同上（**H 股**）
    比亚迪 H 股占 51.3%、宁德 4.9%、招行 18.1%，若被误判成"北向重仓"会完全扭曲画像。
    故用**精确等于** ``香港中央结算有限公司`` 判定北向，H 股单列 ``h_pct`` 只在 UI 备注。

⚠ 时效性（必须在 UI 标注）
    季报数据，报告期滞后最多 1 个季度 + 1 个月披露期（如 2026-09 能看到 2026-06-30）。
    它描述的是**底色**，不是"今天谁在买"。当日行为请结合龙虎榜席位。

本模块会被 CloudBase Python3.7 云函数直接引用，故启用
``from __future__ import annotations`` 以兼容 PEP604 写法（X | None）。
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from quant.data.kline import _http, normalize_code

F10_URL = ("https://emweb.securities.eastmoney.com/PC_HSF10/ShareholderResearch/PageAjax?code=")
_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://emweb.securities.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
}

# 十类（顺序即 UI 展示顺序；"游资" 由龙虎榜补，不在此模块产出）
CATS = ("国家队", "社保基金", "QFII", "险资", "公募基金", "私募", "北向资金", "产业资本", "牛散")

WORKERS = 8            # F10 为逐股接口（190 只需 ~15s）；仅冷启动/季报窗口才全量拉
STALE_DAYS = 7         # 即使报告期未更新，同一只票 7 天内不重复拉（次新股只出半年报）

_NORTH_NAME = "香港中央结算有限公司"          # 精确等于，才是北向
_H_SHARE_KW = ("代理人", "HKSCC", "NOMINEES")  # H 股名义持有人

_NATIONAL_KW = ("中央汇金", "中国证券金融", "证金公司", "汇金资产", "国新投资",
                "国新控股", "中国国新", "中央汇金资产管理")
_INSURANCE_KW = ("人寿保险", "财产保险", "养老保险", "健康保险", "保险资管",
                 "保险股份", "再保险", "保险集团")
_QFII_KW = ("UBS", "摩根士丹利", "摩根大通", "高盛", "巴克莱", "瑞士信贷", "瑞银",
            "花旗", "德意志银行", "美林", "淡马锡", "阿布达比投资局", "科威特政府投资局",
            "新加坡政府投资", "挪威中央银行", "加拿大年金", "野村", "法国巴黎银行",
            "汇丰", "景顺", "富达", "领航", "贝莱德", "GIC", "QFII", "RQFII")
_FUND_TYPES = ("证券投资基金", "基金资产管理计划")
_INSURANCE_TYPES = ("保险产品", "保险公司")
# 前三大股东里命中这些词的，是"资管/基金计划"而非产业资本（实测茅台、平安的伪产业资本）
_NOT_INDUSTRY_KW = ("资管", "资产管理计划", "基金", "信托", "银行")

# `jgcc`（机构持仓汇总）的 ORG_TYPE → 类别。
# ⚠ 该编码是**实测推断**（2026-09-12 用 4 只票交叉验证）：
#     03 隆基 1家 0.44951%  ↔ 社保118组合 0.450%   → 完美吻合
#     05 平安银行 5家 58.7588% ↔ 险资合计 58.759%   → 完美吻合
#     02 宁德 1家 0.6424%   ↔ UBS AG 0.611%        → 吻合（QFII）
#     01 基金家数（茅台 1697 / 宁德 3113）→ 公募基金
#   04 / 07 语义未定（07 占比极大，疑为一般法人），**不使用**。
ORG_MAP = {"01": "公募基金", "02": "QFII", "03": "社保基金", "05": "险资"}

MAX_TOP = 2            # 每类最多保留几个股东名（控制记录体积）


def _num(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def f10_code(code: str) -> str:
    """``sh600519`` → ``SH600519``（东财 F10 的 code 参数格式）。"""
    c = normalize_code(str(code or ""))
    if c.startswith("sh"):
        return "SH" + c[2:]
    if c.startswith(("sz", "bj")):
        return "SZ" + c[2:]
    return ("SH" if c.startswith(("6", "9")) else "SZ") + c


def _ctrl_hit(name: str, ctrl: str | None) -> bool:
    """个人股东是否就是实控人（或实控人成员之一）。

    ``ctrl`` 形如 ``"李振国,李喜燕"``（多人用逗号分隔）或单一机构名。
    隆基的李振国、比亚迪的王传福若被归成"牛散"会严重误导 —— 他们是控股方。
    """
    if not ctrl:
        return False
    for part in str(ctrl).replace("，", ",").split(","):
        p = part.strip()
        if p and (p == str(name) or p in str(name) or str(name) in p):
            return True
    return False


def classify(name: str, htype: str, rank: int, ctrl: str | None = None):
    """单个股东 → (类别 | None, 是否 H 股名义持有人)。

    判定顺序刻意如此：越"特殊"的类别越先匹配，避免被泛化规则吃掉
    （例：``香港中央结算有限公司`` 的 HOLDER_TYPE 也是"其它"，
    若不先判北向就会被产业资本/其它法人吞掉）。
    """
    n = str(name or "")
    t = str(htype or "")

    if any(k in n.upper() or k in n for k in _H_SHARE_KW):
        return None, True
    if n == _NORTH_NAME:
        return "北向资金", False
    if any(k in n for k in _NATIONAL_KW):
        return "国家队", False
    if t == "全国社保基金" or "全国社保基金" in n or "社保基金" in n:
        return "社保基金", False
    if t == "QFII" or any(k in n.upper() or k in n for k in _QFII_KW):
        return "QFII", False
    if t in _INSURANCE_TYPES or any(k in n for k in _INSURANCE_KW):
        return "险资", False
    if t == "私募基金" or "私募" in n:
        return "私募", False
    if t in _FUND_TYPES:
        return "公募基金", False
    if t == "员工持股计划" or "员工持股" in n:
        return "产业资本", False
    # 产业资本：前三大股东里的法人（排除资管/基金计划这类"通道"）
    if rank <= 3 and t in ("投资公司", "其它"):
        if not any(k in n for k in _NOT_INDUSTRY_KW):
            return "产业资本", False
    if t == "个人":
        # ⚠ 创始人/实控人不能算"牛散"（2026-09-12 修正：隆基李振国、比亚迪王传福）
        if rank <= 3 or _ctrl_hit(n, ctrl):
            return "产业资本", False
        return "牛散", False
    return None, False


def build(code: str, raw: dict) -> dict | None:
    """F10 json → 压缩后的画像记录。数据不可用返回 None。"""
    c = normalize_code(str(code or ""))
    rows = raw.get("sdltgd") or []
    if not rows:
        return None

    # 报告期（sdltgd_date 是列表，取最新）
    dates = []
    for d in (raw.get("sdltgd_date") or []):
        v = str((d or {}).get("END_DATE") or "")[:10]
        if v:
            dates.append(v)
    rdate = max(dates) if dates else ""

    cats: dict[str, dict] = {}
    ctrl = None
    h_pct = 0.0

    # 实控人要先取 —— classify 需要它来区分"实控人个人"与"牛散"
    for s in (raw.get("sjkzr") or []):
        v = str(s.get("HOLDER_NAME") or "").strip()
        if v:
            ctrl = v
            break

    for r in rows:
        if str(r.get("END_DATE") or "")[:10] != rdate:
            continue
        nm = str(r.get("HOLDER_NAME") or "").strip()
        ht = str(r.get("HOLDER_TYPE") or "").strip()
        rank = int(_num(r.get("HOLDER_RANK")) or 99)
        pct = _num(r.get("FREE_HOLDNUM_RATIO")) or 0.0
        cat, is_h = classify(nm, ht, rank, ctrl)
        if is_h:
            h_pct += pct
            continue
        if not cat:
            continue
        chg_raw = r.get("HOLD_NUM_CHANGE")
        chg = _num(chg_raw)
        is_new = str(chg_raw or "").strip() == "新进"
        node = cats.setdefault(cat, {"n": 0, "pct": 0.0, "chg": 0.0,
                                     "new": 0, "top": [], "chg_ok": True})
        node["n"] += 1
        node["pct"] += pct
        if chg is not None:
            node["chg"] += chg
        else:
            node["chg_ok"] = False
        if is_new:
            node["new"] += 1
        if len(node["top"]) < MAX_TOP:
            node["top"].append(nm)

    # 全体机构口径（jgcc）：比"十大流通股东"完整得多。
    # 例：茅台进入十大的只有 1 只公募（0.365%），但实际有 1697 只基金合计持 3.60%。
    # ⚠ 与 cats 是**不同口径**，故单列字段 org，不混进 cats（前端分别标注）。
    org: dict[str, dict] = {}
    for g in (raw.get("jgcc") or []):
        if str(g.get("REPORT_DATE") or "")[:10] != rdate:
            continue
        t = str(g.get("ORG_TYPE") or "")
        # ⚠ 循环变量必须叫 cat，不能叫 c —— c 是本函数开头的规范化 code，
        #   2026-09-12 曾因这里遮蔽导致 return 的 "code" 全变 None，
        #   saveHolderRows 的 filter(r=>r.code) 把记录几乎全滤掉。
        cat = ORG_MAP.get(t)
        if not cat:
            continue
        num, ratio = _num(g.get("TOTAL_ORG_NUM")), _num(g.get("TOTAL_SHARES_RATIO"))
        org[cat] = {"n": int(num) if num else None,
                    "pct": round(ratio, 3) if ratio is not None else None}

    # 股东户数（筹码集中度，披露频率高于十大股东）
    focus, hnum, hnum_chg, hnum_date = None, None, None, None
    for g in (raw.get("gdrs") or []):
        focus = str(g.get("HOLD_FOCUS") or "").strip() or None
        hnum = _num(g.get("HOLDER_TOTAL_NUM"))
        hnum_chg = _num(g.get("TOTAL_NUM_RATIO"))
        hnum_date = str(g.get("END_DATE") or "")[:10] or None
        break

    # 十大股东持股变动（临时公告口径，比季报新）
    recent = []
    for s in (raw.get("sdgdcgbd") or [])[:3]:
        chg = _num(s.get("HOLD_CHANGE"))
        recent.append({
            "d": str(s.get("END_DATE") or "")[:10],
            "name": str(s.get("HOLDER_NAME") or "").strip()[:24],
            "chg": chg,
            "pct": _num(s.get("HOLD_NUM_RATIO")),
            "why": str(s.get("CHANGE_REASON") or "").strip()[:8],
        })

    for v in cats.values():
        v["pct"] = round(v["pct"], 3)
        v["chg"] = round(v["chg"] / 1e4, 1) if v.get("chg_ok") else None   # 万股
        v.pop("chg_ok", None)

    rec = {
        "code": c,
        "date": rdate,
        "cats": cats,
        "org": org,
        "ctrl": ctrl,
        "focus": focus,
        "hnum": int(hnum) if hnum else None,
        "hnum_chg": round(hnum_chg, 1) if hnum_chg is not None else None,
        "hnum_date": hnum_date,
        "h_pct": round(h_pct, 2),
        "recent": recent,
        "n": len(rows),
        "tags": derive_tags(cats, org, ctrl, focus, hnum_chg),
    }
    return rec


# ---------------------------------------------------------------- 席位性质（T+0）

def seat_kind(name: str) -> str:
    """龙虎榜席位名 → 资金性质（T+0 口径，与季报底色互补）。

    ⚠ 判定顺序：先 ``机构专用``（东财的笼统机构席位），再 沪深股通专用，
    最后才落到普通营业部（游资）。普通营业部名里确实含"证券"，故
    不能用"证券"作游资判据 —— 它会吃掉机构席位。
    """
    n = str(name or "")
    if "机构专用" in n:
        return "机构专用"
    if "沪股通专用" in n or "深股通专用" in n or "陆股通" in n:
        return "北向专用"
    if n:
        return "游资营业部"
    return "未知"


# ---------------------------------------------------------------- 底色标签

def derive_tags(cats: dict, org: dict, ctrl: str | None,
                focus: str | None, hnum_chg) -> list[str]:
    """把分类结果压成 1~3 个短标签，供票卡上一行扫读。

    阈值刻意偏保守（宁可少标）：标签是"要不要多看一眼"的线索，不是结论。
    机构类优先用 ``org``（全体机构口径，完整），无 ``org`` 时退回 ``cats``
    （十大流通股东口径，会低估）。
    """
    out: list[str] = []

    def pct(k):
        return (cats.get(k) or {}).get("pct") or 0.0

    def n(k):
        return (cats.get(k) or {}).get("n") or 0

    def o_pct(k):
        v = (org.get(k) or {}).get("pct")
        return v if v is not None else None

    def o_n(k):
        return (org.get(k) or {}).get("n") or 0

    def inst(cur, other):
        """取两个口径中的较大值（org 优先，但其缺失时不能当 0）。"""
        return cur if (cur is not None and cur >= (other or 0)) else (other or 0)

    if n("国家队"):
        out.append("国家队")
    if n("社保基金") or o_n("社保基金"):
        out.append("社保持仓")
    if n("QFII") or (o_pct("QFII") or 0) >= 0.3:
        out.append("QFII")
    if inst(o_pct("险资"), pct("险资")) >= 5:
        out.append("险资重仓")
    if pct("北向资金") >= 3:
        out.append("北向重仓")
    elif pct("北向资金") >= 0.5:
        out.append("北向持仓")
    if inst(o_pct("公募基金"), pct("公募基金")) >= 5 or o_n("公募基金") >= 300:
        out.append("公募抱团")
    elif inst(o_pct("公募基金"), pct("公募基金")) >= 2 or o_n("公募基金") >= 80:
        out.append("公募持仓")
    if n("私募") >= 2 or pct("私募") >= 1.5:
        out.append("私募云集")
    if n("产业资本") and ctrl:
        out.append("产业资本控股")
    if n("牛散") >= 3:
        out.append("牛散扎堆")

    if not out:
        if focus and "分散" in focus:
            out.append("筹码分散")
        elif focus and "集中" in focus:
            out.append("筹码集中")
        else:
            out.append("无显著机构")

    # 筹码变化（独立维度，最多再加一个）
    if hnum_chg is not None:
        if hnum_chg <= -10:
            out.append("户数锐减·筹码集中")
        elif hnum_chg >= 15:
            out.append("户数激增·筹码发散")
    return out[:3]


# ---------------------------------------------------------------- 抓取

def fetch_raw(code: str) -> dict:
    """拉一只票的 F10 股东研究原始 json。失败抛异常（调用方决定降级）。"""
    txt = _http(F10_URL + f10_code(code), timeout=15, headers=_UA)
    return json.loads(txt)


def today_str() -> str:
    """北京时间今日（云函数容器为 UTC，统一 +8h）。"""
    import datetime as _dt
    return (_dt.datetime.utcnow() + _dt.timedelta(hours=8)).strftime("%Y-%m-%d")


def query_holders(codes: list, max_workers: int = WORKERS, today: str | None = None) -> dict:
    """并发批量拉取画像。返回 ``{code: rec}``（失败的票直接不出现在结果里）。

    ``rec["fetched"]`` 由本函数写入 —— 它是"抓取日"，与 ``date``（报告期）不同，
    供 :func:`need_refresh` 的防抖使用。
    """
    uniq, seen = [], set()
    for c in codes or []:
        k = normalize_code(str(c or ""))
        if k and k not in seen:
            seen.add(k)
            uniq.append(k)
    if not uniq:
        return {}
    day = today or today_str()

    def work(c):
        try:
            return c, build(c, fetch_raw(c))
        except Exception:
            return c, None

    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for c, rec in ex.map(work, uniq):
            if rec:
                rec["fetched"] = day
            else:
                # 失败占位（北交所 PC_HSF10 不覆盖 / 无数据的次新股）：
                # 也写进缓存，靠 need_refresh 的 fetched 7 天防抖避免每晚白抓重算。
                rec = {"code": c, "failed": 1, "fetched": day}
            out[c] = rec
    return out


# ---------------------------------------------------------------- 新鲜度

def expected_report(today: str) -> str:
    """按今日推「此时应已披露的最新报告期」（YYYY-MM-DD）。

    披露截止：一季报 4/30、半年报 8/31、三季报 10/31、年报次年 4/30。
    故安全的下界是：11 月起看 9-30，9 月起看 6-30，5 月起看 3-31，
    1~4 月只能指望上一年的 9-30（年报与一季报都要到 4 月底才齐）。
    """
    try:
        y, m = int(today[:4]), int(today[5:7])
    except (ValueError, IndexError):
        return ""
    if m >= 11:
        return "%d-09-30" % y
    if m >= 9:
        return "%d-06-30" % y
    if m >= 5:
        return "%d-03-31" % y
    return "%d-09-30" % (y - 1)


def need_refresh(rec: dict | None, today: str) -> bool:
    """是否需要（重新）抓取。

    - 无记录 → 要；
    - 报告期早于 ``expected_report`` → 要（新报告已披露）；
    - 但 ``fetched`` 在 STALE_DAYS 天内 → 不要（次新股只发半年报/年报，
      否则会天天白拉）。
    """
    if not rec:
        return True
    exp = expected_report(today)
    if not exp:
        return False
    if str(rec.get("date") or "") >= exp:
        return False
    return _days_between(str(rec.get("fetched") or ""), today) >= STALE_DAYS


def _days_between(d1: str, d2: str) -> int:
    """两个 YYYY-MM-DD 的天数差；解析失败返回一个大数（视作很久没更新）。"""
    import datetime as _dt
    try:
        a = _dt.date(int(d1[:4]), int(d1[5:7]), int(d1[8:10]))
        b = _dt.date(int(d2[:4]), int(d2[5:7]), int(d2[8:10]))
        return (b - a).days
    except (ValueError, IndexError):
        return 9999


def pick_refresh(codes: list, cache: dict, today: str, force: bool = False) -> list:
    """返回需要抓取的 code 列表（``force=True`` 时全量）。"""
    if force:
        return list(codes or [])
    return [c for c in (codes or []) if need_refresh((cache or {}).get(c), today)]


if __name__ == "__main__":
    import sys
    cs = sys.argv[1:] or ["sh600519", "sz300750", "sh601012"]
    print("expected_report(2026-09-12) =", expected_report("2026-09-12"))
    for c, r in query_holders(cs).items():
        print("%s  报告期=%s  H股=%.2f%%  实控人=%s  户数=%s(%s%%)  %s"
              % (c, r["date"], r["h_pct"], r["ctrl"], r["hnum"], r["hnum_chg"], r["tags"]))
        for k, v in r["cats"].items():
            print("    %-6s n=%d pct=%.3f%% chg=%s 新进%d  %s"
                  % (k, v["n"], v["pct"], v["chg"], v["new"], "/".join(v["top"])))
        for k, v in (r.get("org") or {}).items():
            print("    [全体] %-6s n=%s pct=%s%%" % (k, v["n"], v["pct"]))
