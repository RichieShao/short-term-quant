# -*- coding: utf-8 -*-
"""核心评分卡（P3）。quant/indicators/core_score.py

把《个人关于投机的理解与做法》"地位/谁是核心"量化为 0-100 分。
框架 v0.1 第4节：
  - A 地位与带动性  40分（带动性15 | 首板时序10 | 人气排名10 | 被动性检测5）
  - B 持续性因子    30分（后排厚度10 | 节点质量10 | 板块逻辑强度10）
  - C 风险扣分      30分封顶（一字断层/伪核心一字/连续低开/无利空低开/失去带动/严重异动）

评分 = (A+B−C) 归一化到 0-100 → 等级 S/A/B/C。

数据可得性声明（诚实代理，非分时级精度）：
  - 带动性：用"东财行业当日涨停家数"近似（无法拿到分时联动相关度）
  - 首板时序：用行业涨停池 first_seal 首封排序近似"主动性"
  - 人气排名：用"全市场连板高度位次"近似（龙虎榜/成交额排名无稳定源）
  - 被动性：用炸板次数近似"被反推到涨停"（分时需人工复核）
  - 逻辑强度：无业绩/政策/纯情绪自动判别 → 默认 4/10，人工可用 logic_boost 覆盖
以上偏差在框架第8节"已知边界"声明。

输入：单只候选(涨停池) + 当日全市场涨停池 + 个股近K线 + 可选(昨日池/异动体检/周期阶段)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from quant.data.kline import board_limit
from quant.indicators.abnormal import DeviationResult


# ---------- 配置（阈值集中，P4 校准） ----------

@dataclass
class CoreScoreConfig:
    # A1 带动性：行业当日涨停家数阈值（>=drive_full 给满 15 分）
    drive_full: int = 6
    # A2 主动性：首封排位分档（rank<=1 板块第一封 / rank 前 n_rank_top / 其余）
    rank_top: float = 0.35     # 首封排位处行业前35% → 视为主动
    # B3 板块逻辑强度：人工标注缺省（纯情绪偏下，防机器高估，可覆盖到 10）
    logic_default: float = 4.0
    # C 风险扣分阈值
    one_word_tol: float = 1e-4     # low/high 相对差 < 该值视为一字(全天无波动)
    low_open: float = 0.02         # 低开>=2% 计入连续低开
    gap_big: float = 0.03          # 当日低开>=3% 视为"无利空低开"信号
    low_days: int = 2              # 近3日低开天数达到 → 走弱扣分
    # 扣分值（对应框架4.3）
    p_yizi: float = 10.0           # 一字无换手(筹码断层)
    p_fake_yizi: float = 15.0      # 地位低的伪核心中位股一字
    p_lowopen_no_high: float = 10.0  # 连续低开高走不创新高
    p_gap_low: float = 5.0         # 无利空大低开仍拉板(筹码松动,弱化版)
    p_lose_drive: float = 10.0     # 失去带动性(板块跟风今日锐减)
    p_abnormal: float = 10.0       # 触发/临近严重异动
    risk_cap: float = 30.0


DEFAULT_CS = CoreScoreConfig()

# 等级阈值（0-100，P4 用历史题材回测校准）
GRADE_BANDS = [(80, "S"), (60, "A"), (45, "B"), (0, "C")]


def _grade(total: float) -> str:
    for thr, g in GRADE_BANDS:
        if total >= thr:
            return g
    return "C"


# ---------- 输出结构 ----------

@dataclass
class CoreScore:
    code: str
    name: str
    board_cnt: int                # 连板数
    industry: str                 # 东财行业
    # 分项得分
    a_drive: float = 0.0          # A1 板块带动性 0-15
    a_init: float = 0.0           # A2 主动性/首封时序 0-10
    a_pop: float = 0.0            # A3 人气/市场地位 0-10
    a_passive: float = 0.0        # A4 被动性检测 0-5
    sub_a: float = 0.0            # A 小计 0-40
    b_ladder: float = 0.0         # B1 后排厚度/梯队 0-12
    b_node: float = 0.0           # B2 节点质量 0-8
    b_logic: float = 0.0          # B3 板块逻辑强度 0-10(人工缺省)
    sub_b: float = 0.0            # B 小计 0-30
    risk_items: list = field(default_factory=list)   # [(标签, 扣分, 说明)]
    risk_total: float = 0.0       # 风险扣分合计(<=30)
    total: float = 0.0            # (sub_a+sub_b-risk) 归一 0-100
    grade: str = "C"
    state: str = "观察"            # 状态机标签(近似)
    signals: list = field(default_factory=list)      # 强信号: 一字/退潮/异动等
    notes: list = field(default_factory=list)
    # 派生明细(报告用)
    ind_lu: int = 0               # 行业当日涨停家数
    ind_first_seal_rank: Optional[int] = None  # 行业首封排位
    yizi_days: int = 0            # 自最后一日往前连续一字天数
    dev: Optional[DeviationResult] = None

    @property
    def risk_detail(self) -> str:
        return "；".join(f"{t}{p:.0f}" for t, p, _ in self.risk_items) or "无"


# ---------- 工具 ----------

def _bd(x: dict) -> int:
    """连板数兼容两种键名：涨停池元素用 board_cnt，DailySentiment.leaders 用 board。"""
    v = x.get("board_cnt")
    if not v:
        v = x.get("board")
    return v or 1


def _is_one_word(row: dict, tol: float) -> bool:
    """全天一字：开盘价=最高=最低=收盘(开盘即封,无波动)。用 low==high 判断。"""
    if row.get("low") is None or row.get("high") is None:
        return False
    hi, lo = row["high"], row["low"]
    return abs(hi - lo) <= max(1e-9, hi * tol)


def _pct(row: dict, prev_close: Optional[float]) -> Optional[float]:
    if prev_close:
        return row["close"] / prev_close - 1.0
    return None


def _ind_stats(zt: list[dict], industry: str) -> tuple[int, int, int]:
    """返回 (行业涨停家数, 行业连板家数>=2, 行业内最高板)。industry 空则归未知。"""
    n = conn = maxb = 0
    for x in zt:
        if (x.get("industry") or "未知") == (industry or "未知"):
            n += 1
            b = _bd(x)
            conn += 1 if b >= 2 else 0
            maxb = max(maxb, b)
    return n, conn, maxb


def _seal_rank(zt: list[dict], industry: str, code: str) -> Optional[int]:
    """行业涨停池内按首封时间排序，返回自身排位(1=最先封)；first_seal 缺失不算。"""
    grp = [(x.get("first_seal") or 0, x["code"])
           for x in zt if (x.get("industry") or "未知") == (industry or "未知")
           and x.get("first_seal")]
    grp.sort()
    if not grp:
        return None
    for i, (_, c) in enumerate(grp):
        if c == code:
            return i + 1
    return None  # 自身首封缺失(如昨日连板今日数据无fbt)


def count_prev_industry(prev_zt: list[dict], industry: str) -> int:
    return sum(1 for x in prev_zt if (x.get("industry") or "未知") == (industry or "未知"))


# ---------- 打分 ----------

def score_core(
    ld: dict,                       # {code,name,board_cnt,industry,first_seal,zhaban_cnt,pct}
    zt: list[dict],                 # 当日全市场涨停池
    stock_rows: list[dict],         # 个股近K线(升序,最后=当日)
    *,
    market_max_board: int,          # 全市场最高连板
    stage: str = "",                # 周期阶段(启动/发酵/高潮/震荡/退潮)
    heat: Optional[float] = None,
    prev_zt: Optional[list[dict]] = None,      # 昨日涨停池(算失去带动性)
    dev: Optional[DeviationResult] = None,     # P1 异动体检结果
    cfg: CoreScoreConfig = DEFAULT_CS,
    logic_boost: Optional[float] = None,       # 人工覆盖板块逻辑强度 0-10
) -> CoreScore:
    code = ld["code"]
    name = ld["name"].replace(" ", "")
    industry = ld.get("industry") or "未知"
    board = _bd(ld)

    sc = CoreScore(code=code, name=name, board_cnt=board, industry=industry,
                   dev=dev)

    # 行业统计
    ind_n, ind_conn, ind_maxb = _ind_stats(zt, industry)
    sc.ind_lu = ind_n

    # ---- A1 板块带动性 (0-15)：行业当日涨停家数(跟随者数量) ----
    drive_map = {1: 3.0, 2: 6.0, 3: 9.0, 4: 11.0, 5: 13.0}
    sc.a_drive = drive_map.get(ind_n, 15.0 if ind_n >= cfg.drive_full else 0.0)
    if ind_n == 0:
        sc.a_drive = 0.0
        sc.notes.append("行业涨停数据缺失(东财行业为空)，带动性按独苗处理，需人工补题材")

    # ---- A2 主动性/首封时序 (0-10) ----
    rank = _seal_rank(zt, industry, code)
    sc.ind_first_seal_rank = rank
    if rank is None:
        sc.a_init = 6.0  # 缺首封数据给中值
    elif rank == 1:
        sc.a_init = 10.0
    elif rank <= max(1, int(ind_n * cfg.rank_top)):
        sc.a_init = 8.0
    elif rank <= max(1, int(ind_n * 0.6)):
        sc.a_init = 6.0
    else:
        sc.a_init = 4.0

    # ---- A3 人气/市场地位 (0-10)：全市场连板高度位次 ----
    if board >= market_max_board >= 1:
        sc.a_pop = 10.0
    elif market_max_board - board == 1:
        sc.a_pop = 7.0
    elif market_max_board - board == 2:
        sc.a_pop = 5.0
    else:
        sc.a_pop = 3.0

    # ---- A4 被动性检测 (0-5)：炸板次数近似"被反推/分歧大" ----
    zb = ld.get("zhaban_cnt") or 0
    if zb >= 3:
        sc.a_passive = 0.0
    elif zb == 2:
        sc.a_passive = 1.0
    elif zb == 1:
        sc.a_passive = 2.0
    else:
        sc.a_passive = 4.0
    if zb >= 2:
        sc.notes.append(f"今日{zb}次炸板后回封，分歧大，被动性需分时复核")

    sc.sub_a = min(40.0, sc.a_drive + sc.a_init + sc.a_pop + sc.a_passive)

    # ---- B1 后排厚度/梯队 (0-12) ----
    # ind_conn 含自身；连板梯队越厚持续性越好
    if ind_conn >= 3:
        sc.b_ladder = 12.0
    elif ind_conn == 2:
        sc.b_ladder = 10.0
    elif ind_n >= 4:
        sc.b_ladder = 8.0   # 自身独连板但今日新带出一批首板
    elif ind_n >= 2:
        sc.b_ladder = 6.0
    else:
        sc.b_ladder = 3.0   # 无后排

    # ---- B2 节点质量 (0-8)：与市场节奏共振(用周期阶段近似) ----
    node_map = {"发酵": 8.0, "启动": 7.0, "高潮": 4.0, "震荡": 5.0, "退潮": 2.0}
    sc.b_node = node_map.get(stage, 4.0)
    if stage in ("高潮", "退潮"):
        sc.notes.append(f"{stage}期追高节点差，持续性折价")

    # ---- B3 板块逻辑强度 (0-10)：人工标注缺省低分 ----
    sc.b_logic = cfg.logic_default if logic_boost is None else max(0.0, min(10.0, logic_boost))
    if logic_boost is None:
        sc.notes.append("逻辑强度=缺省4分(纯情绪/无业绩默认低)，人工可按'业绩>政策>情绪'上调至10")

    sc.sub_b = min(30.0, sc.b_ladder + sc.b_node + sc.b_logic)

    # ---- C 风险扣分 (<=30) ----
    limit = board_limit(code, name)
    risk = 0.0
    rows = stock_rows
    if rows:
        last = rows[-1]
        # 一字断层检测：从最后一日起往前数连续一字天数
        yi = 0
        for r in reversed(rows[-6:]):
            if _is_one_word(r, cfg.one_word_tol):
                yi += 1
            else:
                break
        sc.yizi_days = yi
        if yi >= 1:
            if board < market_max_board:
                risk += cfg.p_fake_yizi
                sc.risk_items.append(("伪核心一字", cfg.p_fake_yizi,
                                      f"连{yi}日一字无换手且非市场最高板({market_max_board}板)，大面源泉"))
                sc.signals.append("中位一字")
            else:
                risk += cfg.p_yizi
                sc.risk_items.append(("一字断层", cfg.p_yizi,
                                      f"连{yi}日一字筹码断层，注意板块性一字风险"))
                sc.signals.append("一字断层")

        # 连续低开 + 不创新高（走弱核心特征，需昨日池/多日K）
        low_days = 0
        for i in range(max(1, len(rows) - 4), len(rows) - 1):   # 近3日(不含今日)看低开
            if rows[i]["open"] < rows[i - 1]["close"] * (1 - cfg.low_open):
                low_days += 1
        if low_days >= cfg.low_days:
            hi_prior = max(r["high"] for r in rows[:-1]) if len(rows) > 1 else 0.0
            if last["close"] < hi_prior * 1.0:  # 今日未创区间新高
                risk += cfg.p_lowopen_no_high
                sc.risk_items.append(("连低不新高", cfg.p_lowopen_no_high,
                                      f"近3日{low_days}次低开且未过前高 {hi_prior:.2f}"))
                sc.signals.append("走弱")
        # 当日无利空大低开(筹码松动)
        if len(rows) >= 2:
            pc = rows[-2]["close"]
            if last["open"] < pc * (1 - cfg.gap_big):
                risk += cfg.p_gap_low
                sc.risk_items.append(("大低开拉板", cfg.p_gap_low,
                                      f"今日低开{(pc-last['open'])/pc*100:.1f}%后仍封板，分歧大"))
    else:
        sc.notes.append("无日K数据，一字/低开类风险未判定")

    # 失去带动性：昨日同行业涨停明显多于今日(板块跟风退潮，核心独木难支)
    if prev_zt is not None:
        prev_n = count_prev_industry(prev_zt, industry)
        if prev_n > 0 and ind_n <= max(0, prev_n // 2):
            risk += cfg.p_lose_drive
            sc.risk_items.append(("失去带动", cfg.p_lose_drive,
                                  f"行业涨停 {prev_n}→{ind_n}，跟风退潮只剩核心"))
            sc.signals.append("板块退潮")

    # 严重异动 / 高危接近
    if dev is not None:
        if dev.risk_level in ("严重异动", "高危接近"):
            risk += cfg.p_abnormal
            sc.risk_items.append(("监管异动", cfg.p_abnormal,
                                  f"{dev.risk_level}(10日{dev.dev_10d*100:+.0f}%/30日{dev.dev_30d*100:+.0f}%)"))
            sc.signals.append("监管高危")
        if dev.serious_triggered:
            sc.state = "监管高危"

    sc.risk_total = min(cfg.risk_cap, risk)

    # ---- 汇总：正向(0-70) - 风险后按 70 归一 0-100 ----
    base = sc.sub_a + sc.sub_b            # 0-70
    net = max(0.0, base - sc.risk_total)  # 0-70
    sc.total = round(net / 70.0 * 100.0, 1)
    sc.grade = _grade(sc.total)

    # ---- 状态机(4.4 简化，无分时数据仅近似) ----
    if dev is not None and dev.serious_triggered:
        sc.state = "监管高危(结束预警)"
    elif sc.signals and "中位一字" in sc.signals:
        sc.state = "伪核心·禁接力"
    elif "走弱" in sc.signals:
        sc.state = "走弱(减/剔)"
    elif sc.grade == "S":
        sc.state = "主升核心"
    elif sc.grade == "A":
        sc.state = "核心/主升"
    elif sc.grade == "B":
        sc.state = "次核心/分支"
    else:
        sc.state = "跟风/伪核心"
    return sc


# ---------- 展示 ----------

def render(sc: CoreScore) -> str:
    flag = "🚨" if sc.grade in ("S",) and not sc.risk_items else ""
    return "\n".join([
        f"⭐ {sc.name}({sc.code}) {sc.board_cnt}板 总分 {sc.total:.0f} [{sc.grade}] {sc.state}",
        f"    A地位 {sc.sub_a:.0f}/40 (带动{sc.a_drive:.0f}/15·时序{sc.a_init:.0f}/10·人气{sc.a_pop:.0f}/10·被动{sc.a_passive:.0f}/5)",
        f"    B持续 {sc.sub_b:.0f}/30 (梯队{sc.b_ladder:.0f}/12·节点{sc.b_node:.0f}/8·逻辑{sc.b_logic:.0f}/10)",
        f"    风险 -{sc.risk_total:.0f}/30: {sc.risk_detail or '无'}",
        f"    行业[{sc.industry}] 涨停{sc.ind_lu}家"
        + (f" 首封第{sc.ind_first_seal_rank}" if sc.ind_first_seal_rank else ""),
    ])


def score_for_code(code: str, date: str = "", cfg: CoreScoreConfig = DEFAULT_CS,
                   logic_boost: Optional[float] = None) -> CoreScore:
    """独立 CLI/体检入口：给定标的代码自动抓涨停池+K线→打分（用于人工复核单票）。"""
    from quant.data.kline import (fetch_daily, normalize_code, benchmark_index,
                                  prev_trade_date)
    from quant.data.pools import fetch_zt_pool
    from quant.indicators.sentiment import compute_sentiment
    from quant.indicators.abnormal import compute_deviation

    code = normalize_code(code)
    if not date:
        idx, _ = fetch_daily("sz399001", count=10)
        date = idx[-1]["date"]
    em_date = date.replace("-", "")
    zt = fetch_zt_pool(em_date)
    ld = next((x for x in zt if x["code"] == code), None)
    if ld is None:
        raise ValueError(f"{code} 不在 {date} 涨停池中，无法打分")
    stock_rows, _ = fetch_daily(code, count=80)
    # 市场最高板
    mb = max(_bd(x) for x in zt) if zt else 1
    # 异动体检
    try:
        br, _bn = fetch_daily(benchmark_index(code), count=80)
        dev = compute_deviation(stock_rows, br, code, name=ld["name"],
                                bench_code=benchmark_index(code), bench_name=_bn or "")
    except Exception as e:
        dev = None
        print(f"[warn] 异动体检失败: {e}")
    # 周期阶段
    cur = compute_sentiment(date=date, need_premium=False)
    from quant.regime.cycle import classify
    cyc = classify(cur, None)
    sc = score_core(ld, zt, stock_rows, market_max_board=mb,
                    stage=cyc.stage, heat=cur.heat, dev=dev,
                    cfg=cfg, logic_boost=logic_boost)
    return sc


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    if not target:
        print("用法: python3 -m quant.indicators.core_score 600519 [date]")
        sys.exit(0)
    asof = sys.argv[2] if len(sys.argv) > 2 else ""
    try:
        print(render(score_for_code(target, asof)))
    except Exception as e:
        print(f"打分失败: {e}")
