# -*- coding: utf-8 -*-
"""情绪温度计（P2）。

输入：当日涨停/跌停/炸板池 + 前一交易日涨停池（算隔日溢价）。
输出 DailySentiment：连板高度、梯队、炸板率、溢价、涨跌停家数、情绪温度分。

指标来自框架 v0.1 第3节《情绪温度计与周期定位》：
  连板高度 / 天梯结构 / 涨停跌停家数 / 炸板率 / 昨涨停溢价 / 题材分布。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from quant.data.kline import fetch_daily, fetch_realtime, prev_trade_date
from quant.data.pools import fetch_zt_pool, fetch_dt_pool, fetch_zb_pool


# ---------- 配置 ----------

@dataclass
class SentimentConfig:
    # 情绪温度分 = 加权(涨停家数/高度/连板家数/炸板率/跌停) → 见 heat_score
    # 刻度 = 对应指标给满分的量级。2026-09-02 P4 用 2025-08~2026-09 全年回放校准：
    # 旧值 (70/6/25) 在该市场生态下严重饱和（涨停常 80-150、高板常 10+），
    # 导致温度长期贴顶、全年说不出"退潮"。新刻度取 lu≈p89 / 高度≈p88 / 连板≈p92 分位。
    lu_scale: float = 100.0        # 涨停家数达到该值给满分
    board_scale: float = 13.0      # 最高连板达到该值给满分
    ladder_scale: float = 28.0     # 连板(>=2板)家数达到该值给满分
    ld_penalty_scale: float = 25.0  # 跌停家数达到该值扣满
    # 温度分档（与 CycleConfig 周期线解耦：档位为描述性，阶段由周期判定输出）
    # P4 校准：按 1 年回放 heat 分位近似 p88/p70/p45/p15（离线降级口径，在线约高 5-8 分）
    bands: list = field(default_factory=lambda: [
        (72, "亢奋-高潮"),
        (58, "活跃-发酵"),
        (45, "温和-震荡"),
        (33, "偏冷-分歧"),
        (0, "冰点-退潮"),
    ])


DEFAULT_SC = SentimentConfig()


# ---------- 数据结构 ----------

@dataclass
class DailySentiment:
    date: str                       # 交易日 YYYY-MM-DD
    lu_count: int = 0               # 涨停家数
    ld_count: int = 0               # 跌停家数
    zb_count: int = 0               # 炸板家数
    max_board: int = 0              # 最高连板
    ladder: dict = field(default_factory=dict)   # {n板: 家数}
    conn_board_count: int = 0       # 连板家数(>=2板)
    zhaban_rate: Optional[float] = None     # 炸板率 = 炸板/(涨停+炸板)
    yest_premium: Optional[float] = None    # 昨涨停今日平均涨幅(隔日溢价)
    heat: float = 0.0               # 情绪温度分 0-100
    band: str = ""                  # 温度档位
    top_industries: list = field(default_factory=list)  # [(行业, 家数, 最高板)]
    leaders: list = field(default_factory=list)         # 高标梯队 [{code,name,board,industry}]
    errors: list = field(default_factory=list)


def _fmt_compact(x):
    if isinstance(x, float):
        return f"{x:.0f}"
    return str(x)


def _band(heat: float, cfg: SentimentConfig) -> str:
    for thr, label in cfg.bands:
        if heat >= thr:
            return label
    return cfg.bands[-1][1]


def heat_score(s: "DailySentiment", cfg: SentimentConfig = DEFAULT_SC) -> float:
    """情绪温度分（0-100）——权重 40/20/15/10/15 为框架经验值；
    各分量的"满分刻度"已于 2026-09-02 P4 用 1 年回放校准（见 SentimentConfig）。
    注：缺炸板池(离线回放)时该项不参与、缺隔日溢价给中值 7.5，故离线温度上限 ~82.5，
    在线（含炸板率/真实溢价/跌停惩罚）一般比离线高 5-8 分，分档阈值按离线口径标定。

    权重分配：涨停家数40 | 最高连板20 | 连板家数15 | 炸板率10(反向) | 隔日溢价15
    跌停家数作为反向修正，最多 -20。
    """
    score = 0.0
    score += min(1.0, s.lu_count / cfg.lu_scale) * 40
    score += min(1.0, s.max_board / cfg.board_scale) * 20
    score += min(1.0, s.conn_board_count / cfg.ladder_scale) * 15
    if s.zhaban_rate is not None:
        score += (1.0 - min(1.0, s.zhaban_rate)) * 10
    if s.yest_premium is not None:
        prem = max(-0.05, min(0.08, s.yest_premium))  # 截断 -5%..+8%
        score += (prem + 0.05) / 0.13 * 15
    else:
        score += 7.5  # 缺数据给中值
    # 跌停惩罚：跌停>=25家扣满20分
    score -= min(1.0, s.ld_count / cfg.ld_penalty_scale) * 20
    return round(max(0.0, min(100.0, score)), 1)


def heat_breakdown(s: "DailySentiment", cfg: SentimentConfig = DEFAULT_SC) -> dict:
    """温度构成拆解（2026-09-05）——把 heat_score 的黑箱数字拆成可核对的分项。

    ⚠️ 只做"透明化展示"，**不改任何一分**：分项公式与 heat_score 逐行对齐，
    保证 sum(score) 与 heat_score 一致（仅因 clamp 到 0-100 可能有差值，由 clamped 标注）。
    P4 校准基线完全不受影响。
    """
    parts: list[dict] = []

    def add(key, label, raw, unit, score, max_score, missing=False, note=""):
        # 内部保留高精度（round 3 位），避免逐项取整后累加产生 0.1 级漂移；
        # 展示层再按需要格式化，保证 sum(score) 与 heat_score 完全一致。
        parts.append({
            "key": key, "label": label, "raw": raw, "unit": unit,
            "score": round(score, 3), "max": max_score,
            "ratio": round(score / max_score, 3) if max_score else None,
            "missing": missing, "note": note,
        })

    add("lu", "涨停家数", s.lu_count, "家",
        min(1.0, s.lu_count / cfg.lu_scale) * 40, 40,
        note=f"刻度 {_fmt_compact(cfg.lu_scale)} 家给满")
    add("board", "最高连板", s.max_board, "板",
        min(1.0, s.max_board / cfg.board_scale) * 20, 20,
        note=f"刻度 {_fmt_compact(cfg.board_scale)} 板给满")
    add("conn", "连板家数", s.conn_board_count, "家",
        min(1.0, s.conn_board_count / cfg.ladder_scale) * 15, 15,
        note=f"≥2板，刻度 {_fmt_compact(cfg.ladder_scale)} 家给满")

    if s.zhaban_rate is not None:
        add("zb", "炸板率(反向)", round(s.zhaban_rate, 4), "",
            (1.0 - min(1.0, s.zhaban_rate)) * 10, 10,
            note="炸板率越低分越高")
    else:
        add("zb", "炸板率(反向)", None, "", 0.0, 10, missing=True,
            note="无炸板池 → 该项跳过（离线口径上限因此约 82.5）")

    if s.yest_premium is not None:
        prem = max(-0.05, min(0.08, s.yest_premium))
        add("premium", "昨涨停溢价", round(s.yest_premium, 4), "",
            (prem + 0.05) / 0.13 * 15, 15, note="截断 -5%~+8% 线性映射")
    else:
        add("premium", "昨涨停溢价", None, "", 7.5, 15, missing=True,
            note="无溢价数据 → 给中值 7.5")

    pen = min(1.0, s.ld_count / cfg.ld_penalty_scale) * 20
    parts.append({
        "key": "dt", "label": "跌停惩罚", "raw": s.ld_count, "unit": "家",
        "score": round(-pen, 3), "max": None,
        "ratio": round(pen / 20, 3), "missing": False,
        "note": f"跌停 ≥{_fmt_compact(cfg.ld_penalty_scale)} 家扣满 20 分",
    })

    raw_total = max(0.0, min(100.0, sum(p["score"] for p in parts)))
    return {
        "parts": parts,
        "raw_total": round(sum(p["score"] for p in parts), 3),
        "heat": round(raw_total, 1),
        "clamped": abs(raw_total - sum(p["score"] for p in parts)) > 0.05,
        "missing_keys": [p["key"] for p in parts if p["missing"]],
    }


def heat_percentile(heat: float, hist: list[float]) -> dict:
    """当前温度在历史样本中的分位（p 值 = 低于当前值的占比）。

    诚实降级：样本 < MIN_N 时 ready=False 并回传样本量，前端显示"样本积累中"，
    不拿三五天的数据冒充统计分位。
    """
    # 2026-09-07 下调：东财历史涨停池仅保留约 15 个交易日（实测 08-18 起），
    # 20 日门槛长期无法达成 → 降到 12 提前启用，并在 n<20 时标注 low_sample。
    MIN_N = 12
    hist = [float(x) for x in (hist or []) if isinstance(x, (int, float))]
    n = len(hist)
    if n < MIN_N:
        return {"ready": False, "n": n, "need": MIN_N}
    below = sum(1 for x in hist if x < heat)
    pct = round(below / n * 100, 1)
    return {
        "ready": True, "n": n, "pct": pct,
        # 样本偏少（<20 日）时给出显式标记，前端需标注可信度，避免被当成稳健统计
        "low_sample": n < 20,
        "label": f"高于近 {n} 日中 {pct}% 的交易日" + ("（样本偏少，仅供参考）" if n < 20 else ""),
        "quartile": ("极高区" if pct >= 85 else "偏高区" if pct >= 60
                     else "中位区" if pct >= 35 else "偏低区" if pct >= 15 else "极低区"),
    }


def heat_momentum(series: list) -> dict:
    """温度动量：近 3/5 交易日变化（series 为 DailySentiment 序列，末位为最新）。"""
    hs = [getattr(x, "heat", None) for x in (series or [])]
    hs = [float(x) for x in hs if isinstance(x, (int, float))]
    if not hs:
        return {}
    cur = hs[-1]
    out = {"cur": cur}
    if len(hs) >= 2:
        out["d1"] = round(cur - hs[-2], 1)
    if len(hs) >= 4:
        out["d3"] = round(cur - hs[-4], 1)
    if len(hs) >= 6:
        out["d5"] = round(cur - hs[-6], 1)
    if "d3" in out:
        v = out["d3"]
        out["trend"] = "快速升温" if v >= 8 else "升温" if v >= 3 else \
                       "走平" if v > -3 else "降温" if v > -8 else "快速降温"
    return out


def compute_sentiment_from_pools(
    date: str,
    zt: list[dict],
    dt: list[dict] | None = None,
    zb: list[dict] | None = None,
    yest_premium: Optional[float] = None,
    cfg: SentimentConfig = DEFAULT_SC,
) -> DailySentiment:
    """从已抓取的池数据计算情绪温度（P4 回放与在线报告共用同一口径）。

    zt/dt/zb 为归一化池（含 code/name/board_cnt 或 board/first_seal）。
    yest_premium 为昨涨停今日平均涨幅；历史回放可传 None（则温度给中值）。
    缺少跌停/炸板池时对应项记 0/None（回放降级，见 P4 校准报告说明）。
    """
    dt = dt or []
    zb = zb or []
    s = DailySentiment(
        date=date,
        lu_count=len(zt),
        ld_count=len(dt),
        zb_count=len(zb),
    )
    s.zhaban_rate = s.zb_count / (s.lu_count + s.zb_count) if (s.lu_count + s.zb_count) else 0.0
    if not zb:
        s.zhaban_rate = None  # 无炸板池：不参与打分（保持 None 语义）

    def _bd(x: dict) -> int:
        v = x.get("board_cnt")
        if not v:
            v = x.get("board")
        return v or 1

    # 连板梯队（兼容 board_cnt / board 两种键名）
    boards = [_bd(x) for x in zt if _bd(x)]
    s.max_board = max(boards) if boards else 0
    for n in range(2, s.max_board + 1):
        s.ladder[n] = sum(1 for b in boards if b == n)
    s.conn_board_count = sum(1 for b in boards if b >= 2)

    # 题材分布 & 高标梯队
    ind = {}
    for x in zt:
        i = x.get("industry") or x.get("reason") or "未知"
        e = ind.setdefault(i, {"n": 0, "maxb": 0})
        e["n"] += 1
        e["maxb"] = max(e["maxb"], _bd(x))
    s.top_industries = sorted(
        ((i, e["n"], e["maxb"]) for i, e in ind.items()),
        key=lambda t: (t[1], t[2]), reverse=True)[:6]
    s.leaders = sorted(
        ({"code": x["code"], "name": (x.get("name") or "").replace(" ", ""),
          "board": _bd(x), "industry": x.get("industry") or x.get("reason") or ""}
         for x in zt if _bd(x) >= 2),
        key=lambda d: d["board"], reverse=True)[:12]

    if yest_premium is not None:
        s.yest_premium = yest_premium
    s.heat = heat_score(s, cfg)
    s.band = _band(s.heat, cfg)
    return s


def compute_sentiment(
    date: str = "",                 # YYYY-MM-DD，空=今天
    cfg: SentimentConfig = DEFAULT_SC,
    need_premium: bool = True,
) -> DailySentiment:
    """抓涨停/跌停/炸板池 + 昨涨停溢价，计算当日情绪温度。"""
    # 空 date → 用指数K线推导最近交易日（东财池接口必须带日期）
    if not date:
        try:
            idx_rows, _ = fetch_daily("sz399001", count=10)
            date = idx_rows[-1]["date"] if idx_rows else ""
        except Exception:
            pass
    # date 转东财格式 YYYYMMDD
    em_date = date.replace("-", "") if date else ""
    zt = fetch_zt_pool(em_date)
    dt = fetch_dt_pool(em_date)
    zb = fetch_zb_pool(em_date)

    s = DailySentiment(
        date=date,
        lu_count=len(zt),
        ld_count=len(dt),
        zb_count=len(zb),
    )
    s.zhaban_rate = s.zb_count / (s.lu_count + s.zb_count) if (s.lu_count + s.zb_count) else 0.0

    # 连板梯队
    boards = [x["board_cnt"] for x in zt if x["board_cnt"]]
    s.max_board = max(boards) if boards else 0
    for n in range(2, s.max_board + 1):
        s.ladder[n] = sum(1 for b in boards if b == n)
    s.conn_board_count = sum(1 for b in boards if b >= 2)

    # 题材分布 & 高标梯队
    ind = {}
    for x in zt:
        i = x["industry"] or "未知"
        e = ind.setdefault(i, {"n": 0, "maxb": 0})
        e["n"] += 1
        e["maxb"] = max(e["maxb"], x["board_cnt"])
    s.top_industries = sorted(
        ((i, e["n"], e["maxb"]) for i, e in ind.items()),
        key=lambda t: (t[1], t[2]), reverse=True)[:6]
    s.leaders = sorted(
        ({"code": x["code"], "name": x["name"].replace(" ", ""),
          "board": x["board_cnt"], "industry": x["industry"] or ""}
         for x in zt if x["board_cnt"] >= 2),
        key=lambda d: d["board"], reverse=True)[:12]

    # 隔日溢价：昨日涨停 → 今日表现
    if need_premium:
        try:
            idx_rows, _ = fetch_daily("sz399001", count=30)
            yday = prev_trade_date(idx_rows, asof=date or None)
            if yday:
                yzt = fetch_zt_pool(yday.replace("-", ""))
                codes = [x["code"] for x in yzt][:100]
                if codes:
                    rt = fetch_realtime(codes)
                    pcts = [v["pct"] for k, v in rt.items() if k in codes]
                    s.yest_premium = sum(pcts) / len(pcts) if pcts else None
        except Exception as e:
            s.errors.append(f"隔日溢价计算失败: {e}")

    s.heat = heat_score(s, cfg)
    s.band = _band(s.heat, cfg)
    return s


# ---------- 展示 ----------

def render(s: DailySentiment) -> str:
    lu = s.lu_count
    zb = s.zb_count
    return "\n".join([
        f"🔥 情绪温度计 {s.date}: {s.heat:.0f} 分 [{s.band}]",
        f"    涨停 {lu} | 跌停 {s.ld_count} | 炸板 {zb} (炸板率 {s.zhaban_rate*100:.0f}%)",
        f"    最高连板 {s.max_board} 板 | 连板家数(≥2板) {s.conn_board_count} | 梯队 {dict(s.ladder)}",
        f"    昨涨停隔日溢价 {s.yest_premium*100:+.1f}%" if s.yest_premium is not None else "    昨涨停隔日溢价 数据不可用",
        "    题材: " + "  ".join(f"{i}({n}家/最高{m}板)" for i, n, m in s.top_industries[:4]),
        "    高标: " + "  ".join(f"{x['name']}{x['board']}板" for x in s.leaders[:6]),
    ])
