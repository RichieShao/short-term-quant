# -*- coding: utf-8 -*-
"""双线粘合突破（MA7 / MA21）形态扫描。

口径（2026-09-11 定，用户确认）：
- 数据：腾讯日K，**前复权 qfq**（本项目惯例：前复权仅作形态判断）
- 粘合：|MA7 − MA21| / MA21 ≤ 2.5%，且**连续 ≥3 个交易日**
- 突破：当日 **收盘上穿 MA21**（前一日收盘 ≤ MA21）且 **MA7 上翘**
- 量能确认：当日成交量 ≥ 前 5 日均量 × 1.5 —— 作为**确认旗标**，不参与"突破"判定
- 候选池（2026-09-11 P1 修复）：**当日涨停 ∪ 核心池 ∪ 全市场异动池**
  （异动池 = 东财全市场筛出的"上涨 + 放量/活跃 + 未涨停"，见 `quant/data/universe.py`）。
  修复前只有 涨停 ∪ 核心，而核心池 ⊆ 涨停池 ⇒ ∪ 是空操作，所有"突破"必然是当日涨停股，
  形态退化成"涨停股二次筛选器"，丧失**在涨停之前发现突破**的能力。
- 新鲜度守卫（2026-09-11 P3 修复）：K线最后一根 ≠ 目标交易日的票（停牌/延迟）
  **不产出信号**，只计入 `stale_n` / `stale_codes`；`fresh=False` 供前端提示。

资金流 / 龙虎榜 / 资金性质（2026-09-11 起逐步新增）：
- 资金流（东财）：当日主力净额 + 净占比、超大单/大单拆解、近 3/5 日累计、连续净流入天数；
  **参与排序**（池内百分位），但**不参与突破判定**（不减少命中数）。
- 龙虎榜（东财）：当日榜 `lhb` 与前一交易日榜 `lhb_prev` **两者都存**；
  上榜的加徽章标签，未上榜的按常态处理（`None`）。
  ⚠ 当日榜约 18:00 后才发布 ⇒ 16:05/16:40 快照里 `lhb` 必为空，需 18:00 后的补充任务重算。
- **资金性质「底色」**（2026-09-12 新增，`quant/data/holders.py`）：十大流通股东按
  公募/北向/QFII/社保/险资/私募/产业资本/国家队/牛散分类，挂 `rec["holder"]`。
  这是**季报口径**（滞后最多 1 季度），描述"谁在持有"；当日"谁在买"由龙虎榜席位回答。
  季报数据日内不变 ⇒ 走 `holder_cache` 集合缓存，只对"缓存缺失 / 报告期过期"的票抓取。

说明：本模块会被 CloudBase Python3.7 云函数直接引用，故启用
`from __future__ import annotations` 以兼容 PEP604 写法（X | None）。
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from quant.data.holders import pick_refresh, seat_kind, today_str
from quant.data.news import classify_batch
from quant.data.kline import fetch_daily, normalize_code, prev_trade_date
from quant.data.lhb import fetch_lhb_day, lhb_badges
from quant.data.moneyflow import fill_trend, query_flows, sina_blocked

MA_FAST = 7
MA_SLOW = 21
GLUE_PCT = 0.025      # 粘合阈值：|MA7-MA21|/MA21 ≤ 2.5%
GLUE_DAYS = 3         # 粘合需持续的交易日数
VOL_MULT = 1.5        # 放量确认：成交量 ≥ 前5日均量 × 1.5
MIN_BARS = MA_SLOW + GLUE_DAYS + 3

FLOW_DAYS = 10        # 资金流回看交易日数（覆盖近5日累计 + 连续天数）
# 并发：池子放开到 ~190 只后，资金流成为主要耗时（每只 1~2 个请求）。
# 实测 16 worker 可把 150 只压到 ~15s（云端 120s 预算内）。
FLOW_WORKERS = 16
FLOW_W = (0.5, 0.3, 0.2)   # 资金分权重：当日净占比 / 近3日累计 / 连续净流入
SCAN_WORKERS = 8      # K线并发（池子变大后从 5 提到 8）

PARAMS = {
    "ma_fast": MA_FAST,
    "ma_slow": MA_SLOW,
    "glue_pct": GLUE_PCT,
    "glue_days": GLUE_DAYS,
    "vol_mult": VOL_MULT,
    "fq": "qfq",
    "flow_days": FLOW_DAYS,
    "flow_w": {"ratio": FLOW_W[0], "sum3": FLOW_W[1], "streak": FLOW_W[2]},
    "holder_note": "季报口径（十大流通股东分类），描述'谁在持有'；当日'谁在买'看龙虎榜席位",
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
                  do_flow: bool = True, do_lhb: bool = True,
                  holder_map: dict | None = None,
                  holder_refresh_all: bool = False) -> dict:
    """预取"整池共用"的资金流、龙虎榜与资金性质底色，避免逐股重复请求。

    - 资金流：逐股并发（东财只提供单股接口），带自累积表 ``flow_agg``；
    - 龙虎榜：**按日拉全市场三张表**（明细 / 机构席位 / 营业部席位），
      当日榜约 18:00 后才发布 ⇒ 盘后 16:05/16:40 拉到的 ``lhb`` 必为空，
      需由 21:00 夜间任务重算；``lhb_prev``（T-1，两者都存）任何时点都可用。
    - 资金性质底色（``holder_map``）：季报口径，日内不变 ⇒ 由调用方从
      ``holder_cache`` 读出传入；本函数**只补"缓存缺失 / 报告期过期"的票**，
      并把新抓到的记录放进 ``holder_new`` 由调用方写回。冷启动（首次全池）
      约 15~20s，之后进入季报窗口前都是零开销。
    """
    codes = []
    for it in cands or []:
        c = normalize_code(str(it.get("code") or ""))
        if c:
            codes.append(c)

    ctx = {
        "date": date,
        "flow_map": {}, "flow_meta": None, "agg": flow_agg,
        "lhb": None, "lhb_prev": None, "lhb_errors": [], "prev_date": None,
        "holder": dict(holder_map or {}), "holder_meta": None,
    }

    # ---- 资金性质底色（季报，缓存 + 只报缺口，不在本函数抓取）----
    # ⚠ 抓取**刻意不放在这里**（2026-09-12 踩坑）：一只票的记录约 1KB，190 只 ≈180KB；
    #   若随本次返回一起回传，会撞上"嵌套 callFunction 响应过大被平台截断"，
    #   实测 179 条只回来 10 条（静默，不报错）。而且它会写进 daily 文档，
    #   让接口响应白白膨胀。故本函数只算出**缺口清单**（几十字节/条），
    #   由调用方（daily_job）分批调 ``action=holder_sync`` 抓取后写库，再用完整缓存重算。
    try:
        uniq = list(dict.fromkeys(codes))
        need = pick_refresh(uniq, ctx["holder"], date or today_str(),
                            force=holder_refresh_all)
        ctx["holder_meta"] = {
            "ask_n": len(uniq), "cached_n": len(ctx["holder"]),
            "need_n": len(need), "need": need[:400],
        }
    except Exception as e:
        ctx["holder_meta"] = {"error": "%s: %s" % (type(e).__name__, e)}

    if do_flow:
        try:
            # defer_sina=True：全池先不打新浪（池子放开到 ~190 只会触发限流），
            # 多日趋势留到 scan_pattern 里对"有形态信号的票"按需补拉。
            r = query_flows(codes, days=FLOW_DAYS, agg=flow_agg,
                            max_workers=FLOW_WORKERS, defer_sina=True)
            ctx["flow_map"] = r.get("flows") or {}
            ctx["flow_meta"] = {
                "ask_n": r.get("ask_n"), "hit_n": r.get("hit_n"),
                "srcs": r.get("srcs") or {}, "errors": r.get("errors") or [],
                "days": r.get("days"), "deferred_sina": True,
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


def _seat_kinds(seats_buy: list, seats_sell: list) -> dict:
    """买卖席位按性质归并 → ``{性质: {n, buy, sell, net}}``（净额单位：元）。"""
    out: dict[str, dict] = {}
    for side, rows in (("buy", seats_buy or []), ("sell", seats_sell or [])):
        for s in rows:
            k = seat_kind(s.get("name"))
            d = out.setdefault(k, {"n": 0, "buy": 0.0, "sell": 0.0, "net": 0.0,
                                   "seats": []})
            d["n"] += 1
            b = s.get("buy") or 0.0
            sl = s.get("sell") or 0.0
            d["buy"] += b
            d["sell"] += sl
            d["net"] += (s.get("net") if s.get("net") is not None else (b - sl))
            if len(d["seats"]) < 2 and s.get("name"):
                d["seats"].append(s["name"][:20])
    return out


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
        # 席位按资金性质归并（游资 / 机构专用 / 北向专用）—— T+0 的"谁在买"
        "kinds": _seat_kinds(n.get("seats_buy"), n.get("seats_sell")),
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
    三者先各自做池内百分位（消量纲），再加权。

    **缺失项按可用项自动重归一**（2026-09-11 改，P1 池子放开后的必需护栏）：
    东财多日接口已失效、新浪会反爬限流、自累积表也需数个交易日才成形 ⇒ "近3日/连续"
    经常整体缺失。若仍按原逻辑把缺失项一律当 50 分代入，分数会被压到 25~75 的窄带
    且失去区分度。现改为：
      - ``sum3`` 缺 → 用**当日主力净额**的池内百分位顶替（同向、量纲无关的合理代理）；
      - ``streak`` 缺 → 该因子直接剔除；
      - 剩余权重等比重归一；一项都没有 → 50 分（中性）。
    ``flow_parts`` 透出"实际参与打分的因子数"（1~3），供前端提示可信度。
    """
    ratio = [((r.get("flow") or {}).get("main_ratio")) for r in recs]
    # sum3 缺失时用当日净额当代理 —— 二者同号（净流入为正），且都做池内百分位
    strength = []
    for r in recs:
        f = r.get("flow") or {}
        v = f.get("sum3")
        strength.append(v if v is not None else f.get("main_net"))
    st = [((r.get("flow") or {}).get("streak")) for r in recs]
    pr, p3, ps = _pct_rank(ratio), _pct_rank(strength), _pct_rank(st)
    w1, w2, w3 = FLOW_W
    for i, r in enumerate(recs):
        if not r.get("flow"):
            r["flow_score"] = 50.0
            r["flow_missing"] = True
            r["flow_parts"] = 0
            continue
        parts = []
        if pr[i] is not None:
            parts.append((w1, pr[i]))
        if p3[i] is not None:
            parts.append((w2, p3[i]))
        if ps[i] is not None:
            parts.append((w3, ps[i]))
        if not parts:
            r["flow_score"] = 50.0
            r["flow_missing"] = True
            r["flow_parts"] = 0
            continue
        tw = sum(w for w, _ in parts)
        r["flow_score"] = round(sum(w * v for w, v in parts) / tw, 1)
        r["flow_missing"] = len(parts) < 3
        r["flow_parts"] = len(parts)


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
        # board 只对涨停股有意义（异动池的票当日未涨停，不能显示成"N板"）
        "board": int(item.get("board") or 0),
        "pool": item.get("pool") or "zt",     # zt=涨停池 / core=核心池 / active=全市场异动池
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
    # 资金性质「底色」（季报口径，十大流通股东分类；缺数据为 None）
    rec["holder"] = (ctx.get("holder") or {}).get(code)
    # P3 新鲜度旗标：K线最后一日 != 目标交易日时，形态/资金流日期均可疑
    rec["bar_date"] = d
    rec["stale"] = bool(ctx.get("date") and d != ctx.get("date"))
    return rec


def scan_pattern(cands: list[dict], max_workers: int = SCAN_WORKERS,
                 ctx: dict | None = None, date: str | None = None,
                 flow_agg=None, pool_meta: dict | None = None,
                 holder_map: dict | None = None,
                 holder_refresh_all: bool = False) -> dict:
    """对候选池并发扫描。

    返回 ``{scan_n, hit_n, watch_n, hits, watch, params, errors, time_ms,
    flow_meta, lhb_meta, holder_meta, news_meta, flow_rows, date, latest_bar,
    fresh, stale_n, stale_codes, pool_meta}``

    - ``ctx`` 可由调用方预建（避免与其它模块重复拉取）；缺省时内部构建。
    - 排序（用户口径"资金量参与排序"）：**突破**以资金分为主键、放量为次键；
      **粘合中**仍以粘合天数/粘合度排序（资金分随字段透出，不主导）。
    - 资金流、龙虎榜、资金性质**都不改变突破判定**，命中数不变。
    - ``holder_meta.need``：资金性质缓存里"缺失 / 报告期过期"的 code 清单（通常为空）。
      调用方据此分批抓取并写库后，**用完整缓存再调一次本函数**即可带上底色。
    - **P3 新鲜度守卫**（2026-09-11 修复）：K线最后一根 ≠ 目标交易日的票（停牌 / 行情
      未更新 / 数据延迟）**不产出信号**，只计入 ``stale_n`` / ``stale_codes``。
      修复前这类票会拿旧 bar 静默算出"假突破"，前端看到一个日期对不上的标的却毫无提示。
    """
    t0 = time.time()
    hits: list[dict] = []
    watch: list[dict] = []
    stale_rows: list[dict] = []
    bars: set[str] = set()
    errors: list[str] = []

    items = list(cands or [])
    if ctx is None:
        ctx = build_context(items, date or "", flow_agg=flow_agg,
                            holder_map=holder_map,
                            holder_refresh_all=holder_refresh_all)
    if pool_meta is not None:
        ctx = dict(ctx)
        ctx["pool_meta"] = pool_meta

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
                if r.get("bar_date"):
                    bars.add(r["bar_date"])
                if r.get("stale"):
                    stale_rows.append(r)     # P3：K线日期对不上 → 只计数，不产出信号
                    continue
                if r.get("state") == "突破":
                    hits.append(r)
                else:
                    watch.append(r)

    # 资金分：对"今日全部信号"（突破 + 粘合中）做池内百分位，量纲无关
    allrows = hits + watch
    trend_meta = {}
    if allrows:
        # 多日趋势按需补：只给**信号票**打新浪（全池打会限流 → 整批丢趋势）。
        # agg 自累积可用时零网络开销。
        sig_codes = [r["code"] for r in allrows]
        try:
            patches = fill_trend(ctx.get("flow_map") or {}, sig_codes,
                                 agg=ctx.get("agg"))
        except Exception:
            patches = {}
        for r in allrows:
            p = patches.get(r["code"])
            if p and r.get("flow"):
                r["flow"].update(p)
        trend_meta["signal_n"] = len(sig_codes)
        trend_meta["sina_n"] = len([1 for p in patches.values()
                                    if p.get("trend_src") == "sina"])
        trend_meta["agg_n"] = len([1 for p in patches.values()
                                   if p.get("trend_src") == "agg"])
        trend_meta["sina_blocked"] = bool(sina_blocked())
        # 池内趋势来源分布（非信号票按设计不拉趋势 → 计入 none）
        fm = dict(ctx.get("flow_meta") or {})
        srcs: dict[str, int] = {}
        for c in (ctx.get("flow_map") or {}):
            k = (patches.get(c) or {}).get("trend_src") or "none"
            srcs[k] = srcs.get(k, 0) + 1
        fm["srcs"] = srcs
        fm.update(trend_meta)
        ctx["flow_meta"] = fm
        _flow_score(allrows)

    # ---- 消息面定性（「上涨逻辑」，2026-09-12 新增，quant/data/news.py）----
    # 只对**信号票**（突破 + 粘合观察，约 75 只）抓 T-1 与 T 两天的 F10 资讯：
    # 突破票带 3 条标题明细（~250B/票），粘合票只给标签（~80B/票），合计 ~9KB，
    # 远低于嵌套响应截断线。定性不参与排序与突破判定（与资金流同口径：只展示）。
    news_meta = None
    if allrows and (ctx.get("date") or date):
        try:
            news_map = classify_batch(
                [r["code"] for r in allrows], ctx.get("date") or date,
                ctx.get("prev_date") or "",
                detail_codes=[r["code"] for r in hits])
            for r in allrows:
                r["news"] = news_map.get(r["code"])
            dist: dict[str, int] = {}
            for rec in news_map.values():
                t = rec.get("tag") or "?"
                dist[t] = dist.get(t, 0) + 1
            news_meta = {"ask_n": len(allrows), "ok_n": len(news_map), "dist": dist}
        except Exception as e:
            news_meta = {"error": "%s: %s" % (type(e).__name__, e)}

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
        # ---- 资金性质底色（季报）----
        # 只回"缓存缺口"清单；记录本体由调用方分批 action=holder_sync 抓取（见 build_context 注释）
        "holder_meta": ctx.get("holder_meta"),
        # ---- P3 新鲜度（K线守卫）----
        "date": ctx.get("date") or None,
        "latest_bar": max(bars) if bars else None,   # 池内 K线最新交易日（真实值）
        "fresh": not stale_rows,                     # False = 有票数据滞后，已从信号中剔除
        "stale_n": len(stale_rows),
        "stale_codes": [{"code": r.get("code"), "name": r.get("name"),
                         "bar_date": r.get("bar_date")} for r in stale_rows[:8]],
        # ---- 候选池构成（P1：三源合并）----
        "pool_meta": ctx.get("pool_meta"),
        # ---- 消息面定性（「上涨逻辑」）----
        "news_meta": news_meta,
    }
