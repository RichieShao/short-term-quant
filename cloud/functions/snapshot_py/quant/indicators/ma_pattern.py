# -*- coding: utf-8 -*-
"""双线粘合突破（MA7 / MA21）形态扫描。

口径（2026-09-11 定，用户确认）：
- 数据：腾讯日K，**前复权 qfq**（本项目惯例：前复权仅作形态判断）
- 粘合：|MA7 − MA21| / MA21 ≤ 2.5%，且**连续 ≥3 个交易日**
- 突破：当日 **收盘上穿 MA21**（前一日收盘 ≤ MA21）且 **MA7 上翘**
- 量能确认：当日成交量 ≥ 前 5 日均量 × 1.5 —— 作为**确认旗标**，不参与"突破"判定
- 候选池：当日涨停 ∪ 核心池（与 Lab 同池）

资金流 / 龙虎榜（2026-09-11 新增，用户口径）：
- 资金流（东财）：当日主力净额 + 净占比、超大单/大单拆解、近 3/5 日累计、连续净流入天数；
  **参与排序**（池内百分位），但**不参与突破判定**（不减少命中数）。
- 龙虎榜（东财）：当日榜 `lhb` 与前一交易日榜 `lhb_prev` **两者都存**；
  上榜的加徽章标签，未上榜的按常态处理（`None`）。
  ⚠ 当日榜约 18:00 后才发布 ⇒ 16:05/16:40 快照里 `lhb` 必为空，需 18:00 后的补充任务重算。

说明：本模块会被 CloudBase Python3.7 云函数直接引用，故启用
`from __future__ import annotations` 以兼容 PEP604 写法（X | None）。
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from quant.data.kline import fetch_daily, normalize_code, prev_trade_date
from quant.data.lhb import fetch_lhb_day, lhb_badges
from quant.data.moneyflow import query_flows

MA_FAST = 7
MA_SLOW = 21
GLUE_PCT = 0.025      # 粘合阈值：|MA7-MA21|/MA21 ≤ 2.5%
GLUE_DAYS = 3         # 粘合需持续的交易日数
VOL_MULT = 1.5        # 放量确认：成交量 ≥ 前5日均量 × 1.5
MIN_BARS = MA_SLOW + GLUE_DAYS + 3

FLOW_DAYS = 10        # 资金流回看交易日数（覆盖近5日累计 + 连续天数）
FLOW_WORKERS = 12     # 资金流并发（云端 60s 超时预算内；40 只约 2~4s）
FLOW_W = (0.5, 0.3, 0.2)   # 资金分权重：当日净占比 / 近3日累计 / 连续净流入

PARAMS = {
    "ma_fast": MA_FAST,
    "ma_slow": MA_SLOW,
    "glue_pct": GLUE_PCT,
    "glue_days": GLUE_DAYS,
    "vol_mult": VOL_MULT,
    "fq": "qfq",
    "flow_days": FLOW_DAYS,
    "flow_w": {"ratio": FLOW_W[0], "sum3": FLOW_W[1], "streak": FLOW_W[2]},
    "note": "前复权仅作形态判断；量能为确认旗标；资金流参与排序但不参与突破判定",
}


def _ma(closes: list[float], n: int, i: int):
    """第 i 根（含）的 n 日简单均线；数据不足返回 None。"""
    if i + 1 < n:
        return None
    return sum(closes[i + 1 - n:i + 1]) / float(n)

def _glue(closes: list[float], i: int):
    """返回 (ma7, ma21, 粘合度)；数据不足或 ma21<=0 返回 (None,None,None)。"""
    m7 = _ma(closes, MA_FAST, i)
    m21 = _ma(closes, MA_SLOW, i)
    if m7 is None or m21 is None or m21 <= 0:
        return None, None, None
    return m7, m21, abs(m7 - m21) / m21


# ---------------------------------------------------------------- 资金流 / 龙虎榜 上下文

def build_context(cands: list[dict], date: str, flow_agg=None,
                  do_flow: bool = True, do_lhb: bool = True) -> dict:
    """预取"整池共用"的资金流与龙虎榜，避免逐股重复请求。

    - 资金流：逐股并发（东财只提供单股接口），带自累积表 ``flow_agg``；
    - 龙虎榜：**按日拉全市场三张表**（明细 / 机构席位 / 营业部席位），
      当日榜约 18:00 后才发布 ⇒ 盘后 16:05/16:40 拉到的 ``lhb`` 必为空，
      需由 21:00 夜间任务重算；``lhb_prev``（T-1，两者都存）任何时点都可用。
    """
    codes = []
    for it in cands or []:
        c = normalize_code(str(it.get("code") or ""))
        if c:
            codes.append(c)

    ctx = {
        "date": date,
        "flow_map": {}, "flow_meta": None,
        "lhb": None, "lhb_prev": None, "lhb_errors": [], "prev_date": None,
    }

    if do_flow:
        try:
            r = query_flows(codes, days=FLOW_DAYS, agg=flow_agg,
                            max_workers=FLOW_WORKERS)
            ctx["flow_map"] = r.get("flows") or {}
            ctx["flow_meta"] = {
                "ask_n": r.get("ask_n"), "hit_n": r.get("hit_n"),
                "srcs": r.get("srcs") or {}, "errors": r.get("errors") or [],
                "days": r.get("days"),
            }
        except Exception as e:
            ctx["flow_meta"] = {"error": "%s: %s" % (type(e).__name__, e)}

    if do_lhb and date:
        try:
            idx, _ = fetch_daily("sh000001", count=10)
            ctx["prev_date"] = prev_trade_date(idx, asof=date)
        except Exception:
            ctx["prev_date"] = None
        for key, d in (("lhb", date), ("lhb_prev", ctx["prev_date"])):
            if not d:
                continue
            try:
                ctx[key] = fetch_lhb_day(d)
            except Exception as e:
                ctx["lhb_errors"].append("%s(%s): %s" % (key, d, e))
    return ctx


def _lhb_brief(snap: dict | None, code: str) -> dict | None:
    """把某只票的龙虎榜记录压成前端可用的精简节点；未上榜返回 None（常态处理）。"""
    if not snap or not snap.get("ok"):
        return None
    n = (snap.get("by_code") or {}).get(code)
    if not n:
        return None
    return {
        "on": True,
        "date": n.get("date"),
        "net_amt": n.get("net_amt"),          # 净买额（元），负为净卖
        "buy_amt": n.get("buy_amt"),
        "sell_amt": n.get("sell_amt"),
        "net_ratio": n.get("net_ratio"),      # 净买额占总成交 %
        "deal_ratio": n.get("deal_ratio"),    # 龙虎榜成交占总成交 %
        "accum_amount": n.get("accum_amount"),
        "turnover": n.get("turnover"),
        "pct": n.get("pct"),
        "reasons": n.get("reasons") or [],    # 上榜原因（可能多条）
        "explain": n.get("explain"),          # 东财资金标签
        "n_reason": n.get("n_reason"),
        "inst": n.get("inst"),                # 机构专用席位
        "seats_buy": n.get("seats_buy") or [],
        "seats_sell": n.get("seats_sell") or [],
        "fwd": n.get("fwd") or {},            # 上榜后 1/2/5/10 日涨跌幅
        "tags": lhb_badges(n),                # 徽章短标签
    }


def _pct_rank(vals: list) -> list:
    """0~100 百分位（池内相对排名）；None/非数值 → None（调用方按中性处理）。"""
    out = [None] * len(vals)
    idx = [i for i, v in enumerate(vals) if isinstance(v, (int, float))]
    n = len(idx)
    if not n:
        return out
    for rank, i in enumerate(sorted(idx, key=lambda k: vals[k])):
        out[i] = round(100.0 * rank / (n - 1), 1) if n > 1 else 50.0
    return out


def _flow_score(recs: list[dict]):
    """给每只票打"资金分"（池内百分位加权，0~100）。

    权重 ``FLOW_W`` = 当日主力净占比 / 近3日累计主力净额 / 连续净流入天数。
    三者先各自做池内百分位（消量纲），再加权。无资金数据的按 50（中性）计分并置
    ``flow_missing=True`` —— 即"未知"不奖不罚，原始字段仍原样透出供人工判断。
    """
    ratio = [((r.get("flow") or {}).get("main_ratio")) for r in recs]
    s3 = [((r.get("flow") or {}).get("sum3")) for r in recs]
    st = [((r.get("flow") or {}).get("streak")) for r in recs]
    pr, p3, ps = _pct_rank(ratio), _pct_rank(s3), _pct_rank(st)
    w1, w2, w3 = FLOW_W
    for i, r in enumerate(recs):
        if not r.get("flow"):
            r["flow_score"] = 50.0
            r["flow_missing"] = True
            continue
        a = pr[i] if pr[i] is not None else 50.0
        b = p3[i] if p3[i] is not None else 50.0
        c = ps[i] if ps[i] is not None else 50.0
        r["flow_score"] = round(w1 * a + w2 * b + w3 * c, 1)
        r["flow_missing"] = pr[i] is None


def scan_one(item: dict, ctx: dict | None = None) -> dict | None:
    """扫描单只标的；无信号返回 None。item: {code, name, board, in_core}"""
    code = normalize_code(str(item.get("code") or ""))
    if not code:
        return None

    rows, nm = fetch_daily(code, count=120, fq="qfq")
    if not rows or len(rows) < MIN_BARS:
        return None

    closes = [r["close"] for r in rows]
    vols = [r["volume"] for r in rows]
    i = len(rows) - 1
    d = rows[i]["date"]

    # 粘合布尔序列（索引从 MA_SLOW-1 起才有 MA21）
    glue_ok: dict[int, bool] = {}
    for k in range(MA_SLOW - 1, len(rows)):
        _, _, g = _glue(closes, k)
        glue_ok[k] = bool(g is not None and g <= GLUE_PCT)

    def run_at(k: int) -> int:
        """以 k 为终点向前数连续粘合天数。"""
        n = 0
        while k in glue_ok and glue_ok.get(k):
            n += 1
            k -= 1
        return n

    prev3 = [i - 1, i - 2, i - 3]
    glued_prev = all(glue_ok.get(k) for k in prev3) if (i - 3) >= (MA_SLOW - 1) else False

    m7, m21, glue_now = _glue(closes, i)
    m7p, m21p, _ = _glue(closes, i - 1)
    if m7 is None or m21 is None or m21p is None:
        return None

    close = closes[i]
    prev_close = closes[i - 1]
    pct = (close - prev_close) / prev_close if prev_close else 0.0

    # 突破：当日收盘上穿 MA21 且 MA7 上翘
    breakout = bool(close > m21 and prev_close <= m21p and m7 > m7p)

    # 量能：当日量 / 前5日均量
    base = vols[i - 5:i]
    avg5 = sum(base) / float(len(base)) if base else 0.0
    vol_ratio = (vols[i] / avg5) if avg5 > 0 else None
    vol_ok = bool(vol_ratio is not None and vol_ratio >= VOL_MULT)

    glued_today = bool(glue_now is not None and glue_now <= GLUE_PCT)
    state = ""
    if breakout and glued_prev:
        state = "突破"
    elif glued_today and run_at(i) >= GLUE_DAYS:
        state = "粘合中"

    if not state:
        return None

    rec = {
        "code": code,
        "name": nm or item.get("name") or "",
        "board": int(item.get("board") or 1),
        "in_core": bool(item.get("in_core")),
        "date": d,
        "state": state,
        "close": round(close, 2),
        "pct": round(pct * 100, 2),
        "ma7": round(m7, 3),
        "ma21": round(m21, 3),
        "glue": round((glue_now or 0) * 100, 2),   # 粘合度 %
        "glue_days": run_at(i) if glued_today else run_at(i - 1),
        "vol_ratio": round(vol_ratio, 2) if vol_ratio else None,
        "vol_ok": vol_ok,
    }

    # 资金流 / 龙虎榜挂载（只加字段，不参与突破判定 —— 命中数不变）
    ctx = ctx or {}
    flow = (ctx.get("flow_map") or {}).get(code)
    if flow:
        # K线最后一根不是目标交易日 → 资金流日期对不上，标 stale 供 UI 提示
        flow = dict(flow)
        flow["stale"] = bool(ctx.get("date") and flow.get("date") != ctx.get("date"))
        rec["flow"] = flow
    else:
        rec["flow"] = None
    rec["lhb"] = _lhb_brief(ctx.get("lhb"), code)            # 当日榜（18:00 前为空）
    rec["lhb_prev"] = _lhb_brief(ctx.get("lhb_prev"), code)  # 前一交易日榜（两者都存）
    # P3 新鲜度旗标：K线最后一日 != 目标交易日时，形态/资金流日期均可疑
    rec["bar_date"] = d
    rec["stale"] = bool(ctx.get("date") and d != ctx.get("date"))
    return rec


def scan_pattern(cands: list[dict], max_workers: int = 5,
                 ctx: dict | None = None, date: str | None = None,
                 flow_agg=None) -> dict:
    """对候选池并发扫描。

    返回 ``{scan_n, hit_n, watch_n, hits, watch, params, errors, time_ms,
    flow_meta, lhb_meta, flow_rows}``

    - ``ctx`` 可由调用方预建（避免与其它模块重复拉取）；缺省时内部构建。
    - 排序（用户口径"资金量参与排序"）：**突破**以资金分为主键、放量为次键；
      **粘合中**仍以粘合天数/粘合度排序（资金分随字段透出，不主导）。
    - 资金流与龙虎榜**不改变突破判定**，命中数不变。
    """
    t0 = time.time()
    hits: list[dict] = []
    watch: list[dict] = []
    errors: list[str] = []

    items = list(cands or [])
    if ctx is None:
        ctx = build_context(items, date or "")

    def work(it):
        try:
            return scan_one(it, ctx)
        except Exception as e:  # 单只失败不影响整体
            return {"__err": f"{it.get('code')}: {e}"}

    if items:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for r in ex.map(work, items):
                if not r:
                    continue
                if "__err" in r:
                    errors.append(r["__err"])
                    continue
                if r.get("state") == "突破":
                    hits.append(r)
                else:
                    watch.append(r)

    # 资金分：对"今日全部信号"（突破 + 粘合中）做池内百分位，量纲无关
    allrows = hits + watch
    if allrows:
        _flow_score(allrows)

    # 突破：资金分优先，其次放量、粘合天数、涨幅
    hits.sort(key=lambda r: (-(r.get("flow_score") if r.get("flow_score") is not None else 50),
                             -(r.get("vol_ratio") or 0),
                             -(r.get("glue_days") or 0), -(r.get("pct") or 0)))
    # 粘合中：仍以"粘合天数长 + 粘合紧"为主（未突破前资金分噪声大）
    watch.sort(key=lambda r: (-(r.get("glue_days") or 0), (r.get("glue") or 99)))

    # 落库用的逐日资金流行（daily_job 写 flow_hist）。
    # 取**全池**（含无形态信号的票）以最大化自累积覆盖率——多日累计需要连续样本，
    # 只记信号票会让同一只票隔三差五缺日。只收当日且未 stale 的记录。
    flow_rows = []
    for _c, f in sorted((ctx.get("flow_map") or {}).items()):
        if f and f.get("date") and not f.get("stale"):
            flow_rows.append({
                "code": f["code"], "date": f["date"],
                "m": f["main_net"], "x": f["xl_net"], "l": f["l_net"],
            })

    return {
        "scan_n": len(items),
        "hit_n": len(hits),
        "watch_n": len(watch),
        "hits": hits,
        "watch": watch[:30],
        "params": PARAMS,
        "errors": errors[:8],
        "time_ms": int((time.time() - t0) * 1000),
        "flow_meta": ctx.get("flow_meta"),
        "lhb_meta": {
            "today": (ctx.get("lhb") or {}).get("date"),
            "today_n": (ctx.get("lhb") or {}).get("n_codes"),
            "prev": (ctx.get("lhb_prev") or {}).get("date") or ctx.get("prev_date"),
            "prev_n": (ctx.get("lhb_prev") or {}).get("n_codes"),
            "errors": (ctx.get("lhb_errors") or [])[:4],
        },
        "flow_rows": flow_rows,
    }
