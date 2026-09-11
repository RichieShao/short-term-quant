# -*- coding: utf-8 -*-
"""分析系统 · 实验室（Lab）v2 —— 五道闸门 + 六源真实深度排雷

把 IMA 知识库蒸馏的价值框架（三位一体 × 14维四族 × 六阶段副驾）
压成可对"当日候选池"（题材成分 ∪ 核心池 = 当日涨停全集）批量运行的结构：

  G1 排雷闸（红灯一票否决）→ G2 质地简分(市值/盈利/估值健康)
  → G3 情绪强度(连板 + 核心等级 - 引擎verb风控) → G4 融合 Lab 分 → G5 排序榜

深度数据源（东财 datacenter-web，均已实测可达+新鲜）：
  质押   RPT_CSDC_LIST_NEWEST         全市场周更质押比例(中登口径)
  解禁   RPT_LIFT_STAGE               未来解禁窗口(空=无)
  减持   RPT_SHARE_HOLDER_INCREASE    股东增减持变动(近90天)
  商誉   RPT_F10_FINANCE_GBALANCE     最新财报期 商誉/归母权益
  北向Q  RPT_DMSK_HOLDERS             最新财报期前十大"香港中央结算"持股%+环比(滞后披露)
  北向日 RPT_MUTUAL_TOP10DEAL         每日北向十大成交活跃股(沪股通001/深股通003)成交额
说明：2024-08 后交易所停发北向个股逐日持仓与净买卖（NET_BUY_AMT 恒 null），日度仅剩
      "前十大成交活跃股"的成交额与占比（真实稀疏，无方向）；未上榜 ≠ 无北向交易。

云端 Python3.7 兼容；ThreadPoolExecutor 并发拉源，单次每日任务可控在数秒~十几秒。
"""
from __future__ import annotations

import datetime as _dt
import json
import time
from concurrent.futures import ThreadPoolExecutor

from quant.data.kline import _http, normalize_code

# ---- 权重（0-1，可调；2026-09-07 回放标定）----
# 旧 0.45/0.55（近似平衡）经 141 样本 coretrack 回放验证：r≈0.083 且分层分离弱；
# 网格扫描 W_Q∈[0.20..0.80] 显示「E 主导」单调递增更优（r/ρ 随 W_Q 下降而升，
# 顶部20%−底部20% 分离在 E 倾斜时显著为正）。结论：短线投机收益由情绪/周期定位驱动，
# 基本面质量(Q)为长周期因子，对 T+1 实操收益解释力弱。取 0.30/0.70（指标近峰值、
# 分离 +3.46pp），质地带 30% 仍保留排序区分度；排雷红灯(G1)独立于融合权重，不受影响。
W_Q = 0.30          # 质地分权重（长周期因子，短线弱解释力）
W_E = 0.70          # 情绪强度权重（连板 + 核心 + 周期定位，短线主驱动）

# ---- 质地简分子分上限（合计 100）----
SUB_SCALE = 40      # 规模：总市值
SUB_PROFIT = 35     # 盈利：PE(TTM优先, 缺失回退动态)
SUB_VALUE = 25      # 估值健康：PB

# 板块高度 → 情绪基准（含首板=45，为"刚启动"留下区分度）
E_BOARD = {1: 45, 2: 58, 3: 68, 4: 76, 5: 83, 6: 88}

# verb 风控调整（与引擎动作矩阵同语义）
VERB_PENALTY = {"禁接力": -14, "规避/清仓": -14, "空仓": -6, "减/剔除": -10}

# 候选池规模上限（2026-09-07 加入）：涨停大爆发日（>90家）若全量六源深度扫描，
# Lab 计算时长会从 ~10s 飙到 >40s，触顶 daily_job→snapshot_py 的调用超时。
# 保护规则（确定性，跨日口径一致）：核心池成员全保留；其余按 (板高, 题材, 代码)
# 截断到预算；被截断的标的在榜单外（体检/诊断能力不受影响）。
LAB_POOL_MAX = 50

# ---- 深度排雷阈值（红灯一票否决 / 黄灯提示）----
PLEDGE_RED = 50.0       # 质押 ≥50% 红灯（中登高危区）
PLEDGE_YL = 30.0        # 质押 ≥30% 黄灯
GW_YL = 0.30            # 商誉/归母权益 ≥30% 黄灯
GW_RED = 1.00           # 商誉/归母权益 ≥100% 红灯
LIFT_DAYS = 90          # 解禁观察窗口（未来90天）
REDUCE_DAYS = 90        # 减持观察窗口（近90天）
NORTH_Q_CHG_YL = -1.5   # 季报陆股通持股环比 ≤ -1.5pp 黄灯
LIFT_CAP_MIN = 5e7      # 解禁市值 ≥0.5亿元才提示（LIFT_MARKET_CAP 万元）
NORTH_DAILY_AMT_MIN = 1e9  # 北向十大活跃：成交额 ≥10亿元 才标绿(显著关注)

_DC = "https://datacenter-web.eastmoney.com/api/data/v1/get"


def _num(x):
    if x is None:
        return None
    if isinstance(x, str):
        x = x.strip()
        if x in ("", "-"):
            return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _f(x, nd=2):
    if x is None:
        return None
    try:
        return round(float(x), nd)
    except (TypeError, ValueError):
        return None


def _secid(code: str) -> str:
    c = code.lower()
    if c.startswith("sh"):
        return "1." + c[2:]
    return "0." + (c[2:] if c.startswith(("sz", "bj")) else c)


def _dc_get(report, sort, sort_dir, filt=None, page_size=200, retries=2,
            max_rows=1200, max_page=8):
    """东财 datacenter 通用拉取（翻页+重试）。

    注意：pageSize 过大（部分报表 ≥200）会返回 success=False "服务器繁忙"，
    因此统一保守 page_size 并用翻页补齐；返回行数上限 max_rows 防御。
    """
    url0 = f"{_DC}?reportName={report}&columns=ALL&pageSize={page_size}&pageNumber={{p}}"
    if sort:
        url0 += f"&sortColumns={sort}&sortTypes={sort_dir}"
    if filt:
        url0 += "&filter=" + filt
    out: list = []
    for p in range(1, max_page + 1):
        url = url0.format(p=p)
        got = None
        for _t in range(retries + 1):
            try:
                raw = _http(url, timeout=12.0)
                d = json.loads(raw) if raw else {}
                rows = ((d.get("result") or {}).get("data")) or []
                if rows or d.get("success") is not False:
                    got = rows or []
                    break
            except Exception:
                pass
            time.sleep(0.4)
        if got is None:
            break
        out += got
        if len(got) < page_size or len(out) >= max_rows:
            break
        time.sleep(0.15)
    return out[:max_rows]


def _qf(s: str) -> str:
    """datacenter filter 需 URL 编码的字符集（+ 与 () 保留；实测裸引号/逗号/>=< 会 400）。"""
    for k, v in (('"', "%22"), (",", "%2C"), (">", "%3E"), ("<", "%3C"),
                 ("=", "%3D"), ("'", "%27"), (" ", "+")):
        s = s.replace(k, v)
    return s


def _in_filter(field: str, codes: list, extra: str = "") -> str:
    q = ",".join('"' + c + '"' for c in codes)
    return _qf(f"({field}+in+({q}))" + extra)


def fetch_basic(codes: list[str]) -> dict[str, dict]:
    """轻量行情（东财 ulist）：名称/总市值/PE/PB/换手。分块30+预热+重试。

    坑：push2 对长批量/高频偶发 RemoteDisconnected 整段风控（连单只也会断），
    官方备用域名 push2delay（延迟行情，日级指标无感）可绕过 → 双 host 轮换容灾。
    """
    out: dict[str, dict] = {}
    if not codes:
        return out
    uniq = list(dict.fromkeys(codes))
    hosts = ["push2.eastmoney.com", "push2delay.eastmoney.com"]
    fields = "f2,f3,f8,f9,f12,f14,f20,f23,f115"
    try:  # 预热破冷
        _http(f"https://{hosts[0]}/api/qt/ulist.np/get?fltt=2&invt=2&secids="
              + _secid(uniq[0]) + "&fields=f12,f14", timeout=6.0)
    except Exception:
        pass
    for i in range(0, len(uniq), 30):
        chunk = uniq[i:i + 30]
        url = ("https://%s/api/qt/ulist.np/get?fltt=2&invt=2&secids="
               + ",".join(_secid(c) for c in chunk) + "&fields=" + fields)
        got = None
        for attempt in range(4):
            host = hosts[attempt % len(hosts)]
            try:
                raw = _http(url % host, timeout=10.0)
                data = (json.loads(raw).get("data") or {}) if raw else {}
                diffs = data.get("diff") or []
                if isinstance(diffs, dict):
                    diffs = list(diffs.values())
                if diffs:
                    got = diffs
                    break
            except Exception:
                pass
            time.sleep(0.8 + 0.4 * attempt)
        if not got:
            continue
        for d in got:
            code12 = str(d.get("f12") or "")
            name = str(d.get("f14") or "")
            mv = _num(d.get("f20"))
            pe_ttm = _num(d.get("f115"))
            pe_dyn = _num(d.get("f9"))
            pb = _num(d.get("f23"))
            pe = pe_ttm if pe_ttm is not None else pe_dyn
            out[code12] = {
                "name": name,
                "mv_yi": _f(mv / 1e8, 1) if mv is not None else None,
                "pe": _f(pe, 1),
                "pe_src": "TTM" if pe_ttm is not None else ("动" if pe_dyn is not None else None),
                "pb": _f(pb, 2),
                "turn": _f(_num(d.get("f8")), 1),
                "pct": _f(_num(d.get("f3")), 2),
                "price": _f(_num(d.get("f2")), 2),
            }
        time.sleep(0.15)
    res: dict[str, dict] = {}
    for c in uniq:
        key = c[2:] if c[:2].lower() in ("sh", "sz", "bj") else c
        if key in out:
            res[c] = out[key]
    return res


# ---------------- 六源深度扫描 ----------------
def _bare(c: str) -> str:
    """datacenter 的 SECURITY_CODE 一律无前缀 6 位（sh600519 -> 600519）。"""
    c = c.strip().lower()
    return c[2:] if c[:2] in ("sh", "sz", "bj") else c


def _dl_pledge(codes):
    """质押比例：RPT_CSDC_LIST_NEWEST 每股1行(周更)，TRADE_DATE desc 取最新。空=无质押记录。"""
    codes = [_bare(c) for c in codes]
    res = {}
    for i in range(0, len(codes), 80):
        rows = _dc_get("RPT_CSDC_LIST_NEWEST", "TRADE_DATE", "-1",
                       _in_filter("SECURITY_CODE", codes[i:i + 80]),
                       page_size=200, max_rows=1600)
        for r in rows:
            sc = str(r.get("SECURITY_CODE") or "")
            if sc not in res:
                res[sc] = {"pledge": _num(r.get("PLEDGE_RATIO")),
                           "pledge_date": (r.get("TRADE_DATE") or "")[:10]}
        time.sleep(0.1)
    return res


def _dl_lift(codes, today0):
    """解禁：RPT_LIFT_STAGE 未来窗口，取最早一笔日期与近 LIFT_DAYS 解禁市值(万元)。"""
    codes = [_bare(c) for c in codes]
    end = (today0 + _dt.timedelta(days=LIFT_DAYS)).isoformat()
    extra = f"(FREE_DATE>='{today0.isoformat()}')(FREE_DATE<='{end}')"
    res = {}
    for i in range(0, len(codes), 60):
        rows = _dc_get("RPT_LIFT_STAGE", "FREE_DATE", "1",
                       _in_filter("SECURITY_CODE", codes[i:i + 60], extra),
                       page_size=200, max_rows=1200)
        agg = {}
        for r in rows:
            sc = str(r.get("SECURITY_CODE") or "")
            fd = (r.get("FREE_DATE") or "")[:10]
            if not fd:
                continue
            try:
                fd0 = _dt.date.fromisoformat(fd)
            except ValueError:
                continue
            days = (fd0 - today0).days
            if days < 0 or days > LIFT_DAYS:
                continue
            cap = _num(r.get("LIFT_MARKET_CAP")) or 0  # 万元
            a = agg.setdefault(sc, {"days": LIFT_DAYS + 1, "cap": 0.0, "n": 0})
            a["n"] += 1
            a["cap"] += cap
            if days < a["days"]:
                a["days"] = days
        for sc, a in agg.items():
            res[sc] = {"lift_days": a["days"], "lift_cap_yi": _f(a["cap"] / 1e4, 2),
                       "lift_n": a["n"]}
        time.sleep(0.1)
    return res


def _dl_reduce(codes, today0):
    """股东减持：RPT_SHARE_HOLDER_INCREASE 近 REDUCE_DAYS 天 DIRECTION=减持 合计。"""
    codes = [_bare(c) for c in codes]
    start = (today0 - _dt.timedelta(days=REDUCE_DAYS)).isoformat()
    extra = f"(END_DATE>='{start}')"
    res = {}
    for i in range(0, len(codes), 60):
        rows = _dc_get("RPT_SHARE_HOLDER_INCREASE", "END_DATE", "-1",
                       _in_filter("SECURITY_CODE", codes[i:i + 60], extra),
                       page_size=200, max_rows=1200)
        agg = {}
        for r in rows:
            if (r.get("DIRECTION") or "") != "减持":
                continue
            sc = str(r.get("SECURITY_CODE") or "")
            a = agg.setdefault(sc, {"n": 0, "shares": 0.0, "last": ""})
            a["n"] += 1
            a["shares"] += abs(_num(r.get("CHANGE_NUM_SYMBOL")) or 0)  # 万股
            fd = (r.get("END_DATE") or "")[:10]
            if fd > a["last"]:
                a["last"] = fd
        for sc, a in agg.items():
            res[sc] = {"reduce_n": a["n"], "reduce_shares_wan": _f(a["shares"], 1),
                       "reduce_last": a["last"]}
        time.sleep(0.1)
    return res


def _dl_goodwill(codes):
    """商誉：RPT_F10_FINANCE_GBALANCE 每股最新报告期 GOODWILL / TOTAL_PARENT_EQUITY。

    每股会返回全历史财报期（数十行），限制 REPORT_DATE>=2024 仅需覆盖各股"最新期"
    （所有 A 股 2024 后必有定期报告），避免大分页拖慢每日任务。
    """
    codes = [_bare(c) for c in codes]
    res = {}
    for i in range(0, len(codes), 50):
        rows = _dc_get("RPT_F10_FINANCE_GBALANCE", "REPORT_DATE", "-1",
                       _in_filter("SECURITY_CODE", codes[i:i + 50],
                                  "(REPORT_DATE>='2024-01-01')"),
                       page_size=200, max_rows=1500)
        seen = {}
        for r in rows:  # 每股取最新期
            sc = str(r.get("SECURITY_CODE") or "")
            rd = r.get("REPORT_DATE") or ""
            if sc not in seen or rd > seen[sc]["rd"]:
                seen[sc] = {"rd": rd,
                            "gw": _num(r.get("GOODWILL")),
                            "eq": _num(r.get("TOTAL_PARENT_EQUITY"))}
        for sc, v in seen.items():
            if v["gw"] is None or v["eq"] in (None, 0):
                res[sc] = {"gw_ratio": 0.0, "gw_date": v["rd"][:10]}
            else:
                res[sc] = {"gw_ratio": _f(v["gw"] / v["eq"], 4), "gw_date": v["rd"][:10]}
        time.sleep(0.1)
    return res


def _dl_north_q(codes):
    """北向季报：RPT_DMSK_HOLDERS 最新期(IS_MAX_REPORTDATE=1) 前十大中"香港中央结算"行。"""
    codes = [_bare(c) for c in codes]
    res = {}
    for i in range(0, len(codes), 30):
        filt = _in_filter("SECURITY_CODE", codes[i:i + 30], '(IS_MAX_REPORTDATE="1")')
        rows = _dc_get("RPT_DMSK_HOLDERS", "RANK", "1", filt,
                       page_size=50, max_rows=1200, max_page=6)
        tmp = {}
        for r in rows:
            if "中央" not in (r.get("HOLDER_NAME") or ""):
                continue
            sc = str(r.get("SECURITY_CODE") or "")
            tmp[sc] = {"north_q": _num(r.get("HOLD_RATIO")),
                       "north_chg": _num(r.get("HOLD_RATIO_CHANGE")),
                       "north_end": (r.get("END_DATE") or "")[:10]}
        for sc, v in tmp.items():
            res[sc] = v
        time.sleep(0.1)
    return res


def _dl_north_daily(today0):
    """北向日度：RPT_MUTUAL_TOP10DEAL 沪股通001+深股通003 最新交易日 十大成交活跃股。

    2024-08 起北向净买卖停发（NET_BUY_AMT 恒 null），本源仅剩"上榜 + 成交额(元)"，
    用于呈现北向资金的当日关注标的，不做买卖方向判断（诚实口径见 meta.not_wired）。
    """
    rows1 = _dc_get("RPT_MUTUAL_TOP10DEAL", "TRADE_DATE", "-1",
                    "(MUTUAL_TYPE%3D%22001%22)", page_size=50)
    rows2 = _dc_get("RPT_MUTUAL_TOP10DEAL", "TRADE_DATE", "-1",
                    "(MUTUAL_TYPE%3D%22003%22)", page_size=50)
    best = ""
    for r in rows1 + rows2:
        td = (r.get("TRADE_DATE") or "")[:10]
        if td > best:
            best = td
    out = {"date": "", "by_code": {}}
    if best:
        out["date"] = best
        for r in rows1 + rows2:
            if (r.get("TRADE_DATE") or "")[:10] != best:
                continue
            sc = str(r.get("SECURITY_CODE") or "")
            out["by_code"][sc] = {"amt": _num(r.get("DEAL_AMOUNT")) or 0,
                                  "ratio": _num(r.get("MUTUAL_RATIO")),
                                  "rank": r.get("RANK")}
    return out


def _deep_fetch(codes: list[str], snap_date: str) -> dict[str, dict]:
    """六源并发拉取 → code -> deep 字段（未命中键缺省）。"""
    try:
        today0 = _dt.date.fromisoformat(snap_date or "")
    except ValueError:
        today0 = _dt.date.today()
    uniq = [normalize_code(c) for c in codes]
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = {
            "pledge": ex.submit(_dl_pledge, uniq),
            "lift": ex.submit(_dl_lift, uniq, today0),
            "reduce": ex.submit(_dl_reduce, uniq, today0),
            "gw": ex.submit(_dl_goodwill, uniq),
            "north_q": ex.submit(_dl_north_q, uniq),
            "north_daily": ex.submit(_dl_north_daily, today0),
        }
        for name in futs:
            try:
                futs[name] = futs[name].result(timeout=45)
            except Exception:
                futs[name] = {}
    nd = futs.get("north_daily") or {}
    merged: dict[str, dict] = {}
    for code in uniq:
        key = _bare(code)
        pl = (futs.get("pledge") or {}).get(key) or {}
        lf = (futs.get("lift") or {}).get(key) or {}
        rd = (futs.get("reduce") or {}).get(key) or {}
        gw = (futs.get("gw") or {}).get(key) or {}
        nq = (futs.get("north_q") or {}).get(key) or {}
        ndc = (nd.get("by_code") or {}).get(key) or {}
        merged[code] = {
            "pledge": pl.get("pledge"), "pledge_date": pl.get("pledge_date"),
            "lift_days": lf.get("lift_days"), "lift_cap_yi": lf.get("lift_cap_yi"),
            "lift_n": lf.get("lift_n"),
            "reduce_n": rd.get("reduce_n"), "reduce_shares_wan": rd.get("reduce_shares_wan"),
            "reduce_last": rd.get("reduce_last"),
            "gw_ratio": gw.get("gw_ratio"), "gw_date": gw.get("gw_date"),
            "north_q": nq.get("north_q"), "north_chg": nq.get("north_chg"),
            "north_end": nq.get("north_end"),
            "north_daily_amt": ndc.get("amt"), "north_daily_ratio": ndc.get("ratio"),
            "north_daily_date": nd.get("date"),
        }
    return merged


# ---------------- 评分 ----------------
def _score_scale(mv_yi):
    if mv_yi is None:
        return None
    if mv_yi >= 500:
        return 40
    if mv_yi >= 200:
        return 36
    if mv_yi >= 100:
        return 31
    if mv_yi >= 60:
        return 25
    if mv_yi >= 30:
        return 19
    if mv_yi >= 15:
        return 13
    return 8


def _score_profit(pe):
    if pe is None:
        return None
    if pe <= 0:
        return 10
    if pe < 20:
        return 35
    if pe < 40:
        return 32
    if pe < 70:
        return 27
    if pe < 120:
        return 21
    if pe < 200:
        return 16
    return 11


def _score_value(pb):
    if pb is None:
        return None
    if pb <= 1.5:
        return 25
    if pb <= 3:
        return 22
    if pb <= 5:
        return 18
    if pb <= 8:
        return 13
    if pb <= 12:
        return 9
    return 5


def _q_quality(basic: dict) -> tuple:
    mv_yi = basic.get("mv_yi")
    pe = basic.get("pe")
    pb = basic.get("pb")
    parts = [(_score_scale(mv_yi), SUB_SCALE, "市值"),
             (_score_profit(pe), SUB_PROFIT, "盈利"),
             (_score_value(pb), SUB_VALUE, "估值")]
    got = [(s, w, n) for (s, w, n) in parts if s is not None]
    if not got:
        return None, [n for (_s, _w, n) in parts]
    total = round(sum(s for s, _w, _n in got) / sum(w for _s, w, _n in got) * 100)
    missing = [n for (_s, _w, n) in parts if _s is None]
    return total, missing


def _q_tag(q):
    if q is None:
        return "缺数据"
    if q >= 75:
        return "质地优"
    if q >= 60:
        return "质地良"
    if q >= 45:
        return "质地中"
    return "质地弱"


def _e_score(board, in_core, grade, verb, stage=None) -> int:
    """情绪强度：连板高度基准 + 核心A/B级加成 − 引擎verb风控 + 周期定位调节。

    周期定位调节（框架核心假设「周期定位×核心识别」，已被 coretrack 回放证实有效：
    启动+4.70% > 震荡+2.31% > 高潮+0.78% > 发酵+0.55% > 退潮+0.22%）：
      stage=None（缺周期上下文，回测/异常）→ 不调节，保持原线性基准；
      启动/发酵：早期可追，小幅加成；
      高潮：高位(连板≥4)拥挤、次日高开低走(回测印证)，按板高递减惩罚（不接力中位补涨）；
      退潮：框架要求空仓，强惩罚。
    """
    e = E_BOARD.get(int(board or 1), 92)
    if in_core and grade in ("A", "B"):
        e += 10
    if verb:
        e += VERB_PENALTY.get(verb, 0)
    if stage == "启动":
        e += 6
    elif stage == "发酵":
        e += 3
    elif stage == "高潮":
        e -= max(0, int(board or 1) - 3) * 5
    elif stage == "退潮":
        e -= 16
    return max(20, min(95, e))


def _stage_of(date):
    """周期定位（懒算，仅供 Lab 情绪调节）：与日快照同源同口径（6 日窗口 classify）。

    缺日期/算不出 → None（E 不调节，回退到原始线性基准，保证不崩）。
    """
    if not date:
        return None
    try:
        from quant.indicators.sentiment import compute_sentiment
        from quant.regime.cycle import classify
        from quant.report.daily import _trade_dates
        dates = [x for x in _trade_dates(8) if x <= date][-6:]
        if not dates:
            dates = [x for x in _trade_dates(260) if x <= date][-6:]
        if not dates:
            return None
        series = [compute_sentiment(date=dd) for dd in dates]
        cyc = classify(series[-1], series[-2] if len(series) >= 2 else None)
        return cyc.stage
    except Exception:
        return None


def _deep_flags(d: dict) -> tuple:
    """深度源 → (红灯/黄灯 flags, 正向绿标 greens)。"""
    flags, greens = [], []
    pl = d.get("pledge")
    if pl is not None:
        if pl >= PLEDGE_RED:
            flags.append({"lv": "red",
                          "t": f"股权质押 {pl:.0f}%（中登周更 {d.get('pledge_date')}，强平高危）"})
        elif pl >= PLEDGE_YL:
            flags.append({"lv": "yellow", "t": f"股权质押 {pl:.0f}%（{d.get('pledge_date')}）"})
    gw = d.get("gw_ratio")
    if gw is not None and gw >= GW_RED:
        flags.append({"lv": "red",
                      "t": f"商誉达归母权益 {gw*100:.0f}%（减值可重创，{d.get('gw_date')}）"})
    elif gw is not None and gw >= GW_YL:
        flags.append({"lv": "yellow",
                      "t": f"商誉/归母权益 {gw*100:.0f}%（减值风险，{d.get('gw_date')}）"})
    if d.get("lift_n"):
        if d.get("lift_cap_yi") is not None and d["lift_cap_yi"] >= LIFT_CAP_MIN / 1e8:
            flags.append({"lv": "yellow",
                          "t": f"{d['lift_days']} 天后解禁 ≈{d['lift_cap_yi']}亿元（{d['lift_n']}笔）"})
        else:
            flags.append({"lv": "yellow", "t": f"{d['lift_days']} 天后有 {d['lift_n']} 笔解禁"})
    if d.get("reduce_n"):
        flags.append({"lv": "yellow",
                      "t": f"近{REDUCE_DAYS}天 {d['reduce_n']} 起股东减持"
                           f"（约{d.get('reduce_shares_wan')}万股，截至{d.get('reduce_last')}）"})
    nc = d.get("north_chg")
    if nc is not None and nc <= NORTH_Q_CHG_YL:
        flags.append({"lv": "yellow",
                      "t": f"北向(季报)持股环比 {nc:+.2f}pp（至{d.get('north_end')}）"})
    n_amt = d.get("north_daily_amt")
    if n_amt is not None and n_amt >= NORTH_DAILY_AMT_MIN:
        greens.append({"t": f"北向十大活跃·成交{n_amt/1e8:.0f}亿",
                       "date": d.get("north_daily_date")})
    return flags, greens


def _note(row: dict) -> str:
    if row.get("veto"):
        return "排雷红灯，直接排除，不做任何接力"
    verb = row.get("verb") or ""
    q_tag = _q_tag(row.get("q"))
    b = row.get("board")
    if verb in ("禁接力", "规避/清仓"):
        return f"引擎{verb}：即使 Lab 分高也不参与（退潮/监管语境）"
    if row.get("in_core") and b >= 4 and verb not in ("禁接力", "规避/清仓"):
        return f"高标核心({b}板)：情绪强 · {q_tag}"
    if b == 1 and row.get("q") is not None and row.get("q") >= 60:
        return "低位首板 + 质地尚可：可作启动候选跟踪"
    if row.get("pe") is not None and row.get("pe") < 0 and b >= 2:
        return f"连板({b}板)但当期亏损：纯情绪，禁中位接力"
    return f"{b}板 · {row.get('industry') or '—'} · {q_tag}"


def build_lab(zt_today: list[dict], cores: list[dict],
              per_stock: list[dict] | None = None,
              date: str | None = None, stage: str | None = None) -> dict:
    """候选 = 当日全部题材成分（涨停全集）∪ 核心池，去重后六源深度扫描 + 打分排序。"""
    t0 = time.time()
    # 周期定位（情绪调节依据）：显式传入优先（日快照已算，零成本），否则懒算（回测/独立调用）。
    stage = stage or _stage_of(date)
    core_by_code = {c.get("code"): c for c in (cores or [])}
    verb_by_code = {p.get("code"): p.get("verb") for p in (per_stock or [])}
    cand_map: dict[str, dict] = {}
    for x in zt_today:
        code = normalize_code(x.get("code", ""))
        cand_map[code] = {
            "code": code, "name": x.get("name", ""),
            "industry": (x.get("industry") or "").strip(),
            "board": int(x.get("board_cnt") or 1),
            "zttj": x.get("zttj") or "",
            "in_core": code in core_by_code,
            "grade": (core_by_code.get(code) or {}).get("grade"),
            "verb": verb_by_code.get(code, ""),
        }
    for c in cores or []:
        code = normalize_code(c.get("code", ""))
        if code not in cand_map:
            cand_map[code] = {
                "code": code, "name": c.get("name", ""),
                "industry": c.get("industry", "") or "",
                "board": int(c.get("board") or 1), "zttj": "",
                "in_core": True, "grade": c.get("grade"),
                "verb": verb_by_code.get(code, ""),
            }
    codes = list(cand_map.keys())
    truncated = 0
    if len(codes) > LAB_POOL_MAX:
        core = [c for c in cand_map.values() if c.get("in_core")]
        rest = sorted((c for c in cand_map.values() if not c.get("in_core")),
                      key=lambda c: (-int(c.get("board") or 1),
                                     c.get("industry") or "", c.get("code") or ""))
        budget = LAB_POOL_MAX - len(core)
        if budget < 0:
            budget = 0
        keep = core + rest[:budget]
        cand_map = {c["code"]: c for c in keep}
        truncated = len(codes) - len(keep)
        codes = list(cand_map.keys())
    basics = fetch_basic(codes)
    deeps = _deep_fetch(codes, date or "")

    vetoed, ranks, missing_n = [], [], 0
    for code, row in cand_map.items():
        basic = basics.get(code) or {}
        d = deeps.get(code) or {}
        out = dict(row)
        out.update(d)  # deep 字段平铺：pledge/gw_ratio/lift_*/reduce_*/north_*
        out["basic_ok"] = bool(basic)
        out["mv_yi"] = basic.get("mv_yi")
        out["pe"] = basic.get("pe")
        out["pe_src"] = basic.get("pe_src")
        out["pb"] = basic.get("pb")
        out["turn"] = basic.get("turn")
        out["pct"] = basic.get("pct")
        out["price"] = basic.get("price")
        # 基础黄灯（亏损/小微/高估/高换手）
        flags = []
        name_lc = (basic.get("name") or out.get("name") or "").lower()
        if "st" in name_lc:
            flags.append({"lv": "red", "t": "ST/*ST 退市风险警示（一票否决）"})
        if out.get("pe") is not None and out["pe"] < 0:
            flags.append({"lv": "yellow", "t": "当期亏损 PE<0（估值失真）"})
        if out.get("mv_yi") is not None and out["mv_yi"] < 30:
            flags.append({"lv": "yellow", "t": f"小微市值 {out['mv_yi']}亿（壳/纯题材概率高）"})
        if out.get("pe") is not None and out["pe"] > 150:
            flags.append({"lv": "yellow", "t": "估值过高 PE>150"})
        if out.get("pb") is not None and out["pb"] > 10:
            flags.append({"lv": "yellow", "t": "估值过高 PB>10"})
        if out.get("turn") is not None and out["turn"] > 40:
            flags.append({"lv": "yellow", "t": f"超高热换手 {out['turn']}%（高位分歧）"})
        # 深度红灯/黄灯 + 正向绿标
        df, greens = _deep_flags(out)
        flags += df
        out["flags"] = flags
        out["greens"] = greens
        reds = [f for f in flags if f["lv"] == "red"]
        out["veto"] = bool(reds)
        out["veto_reason"] = "；".join(f["t"] for f in reds)
        q, q_missing = _q_quality(basic)
        out["q"] = q
        out["q_missing"] = q_missing
        out["e"] = _e_score(out["board"], out["in_core"], out.get("grade"), out.get("verb"), stage)
        out["lab"] = None if q is None else round(q * W_Q + out["e"] * W_E)
        out["note"] = _note(out)
        if not basic:
            missing_n += 1
        if out["veto"]:
            out["lab"] = None  # 否决票不参排名，lab 置空，避免与重算路径 schema 不一致、前端也不读
            vetoed.append(out)
        else:
            ranks.append(out)

    ranks.sort(key=lambda r: (r["lab"] if r["lab"] is not None else -1), reverse=True)
    vetoed.sort(key=lambda r: (r["board"]), reverse=True)
    nd_date = None
    for c in deeps:
        if deeps[c].get("north_daily_date"):
            nd_date = deeps[c]["north_daily_date"]
            break
    return {
        "date": date,
        "pool_n": len(codes),
        "pool_cap": LAB_POOL_MAX,
        "pool_truncated": truncated,
        "veto_n": len(vetoed),
        "missing_n": missing_n,
        "ranks_n": len(ranks),
        "weights": {"q": W_Q, "e": W_E},
            "stage": stage,
            "meta": {
                "g1": ("排雷闸：ST/*ST、质押≥50%、商誉≥归母权益100% → 一票否决；"
                       "黄灯：质押30-50%、商誉≥30%、未来90天解禁、近90天股东减持、北向(季报)持股明显下降"),
                "q_note": f"质地简分({SUB_SCALE}+{SUB_PROFIT}+{SUB_VALUE})：市值/盈利(PE)/估值健康(PB)，"
                          "缺项按可得子项归一，缺数据不假装",
                "e_note": ("情绪强度：连板高度基准 + 核心A/B级加成 − 引擎verb风控(禁接力/规避/空仓)"
                           " + 周期定位调节(启动/发酵加成、高潮高位递减惩罚、退潮强惩罚)，"
                           "与框架「周期定位×核心识别」一致"),
                "sources": {
                    "质押": "中登股权质押周更（周度快照）",
                    "解禁": "未来90天限售解禁",
                    "减持": "近90天股东减持",
                    "商誉": "最新财报期 商誉/归母权益",
                    "北向": "季报香港中央结算持股(滞后披露，比例+环比) + 每日十大成交活跃股(成交额口径)",
                },
                "not_wired": ["北向个股逐日持仓与净买卖 2024-08 后交易所停发，日度仅前十大成交活跃股"
                              "（只含成交额，无买卖方向；未上榜≠无北向交易）"],
                "north_daily_date": nd_date,
            },
        "time_ms": round((time.time() - t0) * 1000),
        "vetoed": vetoed,
        "ranks": ranks,
    }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from quant.data.pools import fetch_zt_pool
    d = sys.argv[1] if len(sys.argv) > 1 else ""
    zt = fetch_zt_pool(d)
    lab = build_lab(zt, [], date=d or None)
    print(f"pool {lab['pool_n']} veto {lab['veto_n']} missing {lab['missing_n']} "
          f"ranks {lab['ranks_n']} {lab['time_ms']}ms")
    for r in lab["ranks"][:8]:
        print(f"  {r['name']:<6} b{r['board']} q={r['q']} e={r['e']} lab={r['lab']} "
              f"质押={r.get('pledge')} 商誉={r.get('gw_ratio')} 解禁={r.get('lift_days')} "
              f"减持={r.get('reduce_n')} 北Q={r.get('north_q')}({r.get('north_chg')}) "
              f"北日成交={r.get('north_daily_amt')} | {r['note']}")
    for v in lab["vetoed"][:5]:
        print("  VETO", v["name"], v["veto_reason"])
