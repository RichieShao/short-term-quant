# -*- coding: utf-8 -*-
"""异动偏离值引擎（P1 + 下跌侧 & 同向规则补充）。

基于舒九《个人关于投机的理解与做法》监管规则 + 沪深北交易所真实规则蒸馏：

普通异动(3日窗口，取连续交易日)：
  - 10cm 主板：3日累计偏离 >= ±20%
  - 20cm 创业/科创：3日累计偏离 >= ±30%
  - ST(5cm)：3日累计偏离 >= ±15%
严重异动（上涨/下跌双侧）：
  - 10日累计偏离 >= +100%（上涨）或 <= -50%（下跌）
  - 30日累计偏离 >= +200%（上涨）或 <= -70%（下跌）
  - 10个交易日内 4 次同向普通异动（补充规则）

偏离值定义（舒九原文示例口径）：偏离值 = 区间个股涨幅 - 区间指数涨幅（均按复合区间涨幅）。
  例：10天涨110%、指数涨20% → 偏离 = 90% < 100%，不触发严重异动。
窗口对齐：个股与基准指数取"最近N个共同交易日"。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from quant.data.kline import board_limit, normalize_code


# ---------- 规则配置（可调阈值都集中在这里，便于后续回测校准） ----------

@dataclass
class AbnormalConfig:
    # 普通异动：3日累计偏离阈值（按涨跌停板幅度区分）
    threshold_3d_10cm: float = 0.20     # 主板
    threshold_3d_20cm: float = 0.30     # 创业板 / 科创板
    threshold_3d_st: float = 0.15       # ST（5cm）
    # 严重异动：上涨侧 / 下跌侧
    threshold_10d_up: float = 1.00      # 10日累计偏离 +100%
    threshold_10d_down: float = -0.50   # 10日累计偏离 -50%
    threshold_30d_up: float = 2.00      # 30日累计偏离 +200%
    threshold_30d_down: float = -0.70   # 30日累计偏离 -70%
    # 10日内同向普通异动计数触发严重异动
    same_dir_days: int = 10             # 观察窗口(交易日)
    same_dir_count: int = 4             # 达到次数
    # 预警余量：偏离值距阈值小于该比例(相对阈值绝对值)时标记"接近异动"
    warn_margin: float = 0.15
    # 窗口
    win_3d: int = 3
    win_10d: int = 10
    win_30d: int = 30


DEFAULT_CFG = AbnormalConfig()


# ---------- 输出结构 ----------

@dataclass
class DeviationResult:
    code: str
    name: str
    limit_pct: float            # 涨跌停幅度小数 0.10/0.20/0.30
    board: str                  # 主板/创业板/科创板/ST等
    bench: str                  # 基准指数代码
    bench_name: str = ""
    # 累计偏离（个股累计涨幅 - 指数累计涨幅，逐日差累加）
    dev_3d: Optional[float] = None
    dev_10d: Optional[float] = None
    dev_30d: Optional[float] = None
    # 纯个股累计涨幅
    stock_3d: Optional[float] = None
    stock_10d: Optional[float] = None
    stock_30d: Optional[float] = None
    # 近10日/30日涨停次数
    limitup_10d: int = 0
    limitup_30d: int = 0
    # 信号
    normal_3d_triggered: bool = False
    serious_10d_up: bool = False
    serious_10d_down: bool = False
    serious_30d_up: bool = False
    serious_30d_down: bool = False
    # 10日内同向普通异动次数（达到4次构成严重异动）
    same_dir_up_count: int = 0
    same_dir_down_count: int = 0
    # 接近严重异动（任意一侧余量不足）
    near_serious: bool = False
    headroom_10d_up: Optional[float] = None
    headroom_10d_down: Optional[float] = None
    headroom_30d_up: Optional[float] = None
    headroom_30d_down: Optional[float] = None
    last_date: str = ""
    notes: list = field(default_factory=list)

    @property
    def serious_triggered(self) -> bool:
        return (self.serious_10d_up or self.serious_10d_down
                or self.serious_30d_up or self.serious_30d_down
                or self.same_dir_up_count >= 4 or self.same_dir_down_count >= 4)

    @property
    def risk_level(self) -> str:
        if self.serious_triggered:
            return "严重异动"
        if self.normal_3d_triggered:
            return "普通异动"
        if self.near_serious:
            return "高危接近"
        return "正常"


def _daily_pct(closes: list[float]) -> list[float]:
    """逐日涨跌幅序列（长度 n-1）。"""
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]


def _cum_stock(closes: list[float], n: int) -> Optional[float]:
    if len(closes) < n + 1:
        return None
    return closes[-1] / closes[-(n + 1)] - 1.0


def _count_limitup(closes: list[float], limit: float, n: int) -> int:
    """近n日收盘涨停次数（涨停=当日涨幅>=涨停幅度*0.999 容差）。"""
    if len(closes) < 2:
        return 0
    pcts = _daily_pct(closes)
    cnt = 0
    for p in pcts[-n:]:
        if p >= limit * 0.999:
            cnt += 1
    return cnt


def classify_board(code: str, name: str = "") -> tuple[str, float]:
    """返回 (板块标签, 涨停幅度小数)。"""
    code = normalize_code(code)
    nm = name or ""
    st = "ST" in nm.upper()
    if st:
        return ("ST", 0.05)
    c = code[2:]
    if c.startswith(("300", "301", "302")) or c.startswith(("688", "689")):
        return ("创业/科创", 0.20)
    if code.startswith("bj"):
        return ("北交所", 0.30)
    if code.startswith("sh") and c.startswith("6"):
        return ("沪主板", 0.10)
    if code.startswith("sz") and c.startswith("0"):
        return ("深主板", 0.10)
    return ("其他", board_limit(code, nm))


def compute_deviation(
    stock_rows: list[dict],
    bench_rows: list[dict],
    code: str,
    name: str = "",
    cfg: AbnormalConfig = DEFAULT_CFG,
    limit_pct: Optional[float] = None,
    bench_code: str = "",
    bench_name: str = "",
) -> DeviationResult:
    """核心计算：个股日线与基准指数日线按日期对齐，复合区间涨幅差。

    偏离值 = (个股区间涨幅) - (指数区间涨幅)，与舒九原文示例一致。
    stock_rows / bench_rows 均为升序 [{date, close}]。
    """
    code = normalize_code(code)
    s_by_date = {r["date"]: r["close"] for r in stock_rows}
    b_by_date = {r["date"]: r["close"] for r in bench_rows}
    common_dates = sorted(set(s_by_date) & set(b_by_date))
    if len(common_dates) < 2:
        raise ValueError(f"{code} 与基准指数共同交易日不足")

    board, default_limit = classify_board(code, name)
    limit = limit_pct if limit_pct is not None else default_limit

    s_closes = [s_by_date[d] for d in common_dates]
    b_closes = [b_by_date[d] for d in common_dates]

    res = DeviationResult(
        code=code, name=name or code, limit_pct=limit, board=board,
        bench=bench_code or code, bench_name=bench_name,
        last_date=common_dates[-1],
    )

    if board == "ST":
        thr_3d = cfg.threshold_3d_st
    elif limit >= 0.20 - 1e-9:
        thr_3d = cfg.threshold_3d_20cm
    else:
        thr_3d = cfg.threshold_3d_10cm

    # 累计偏离 = 区间复合涨幅差（与舒九原文示例一致：个股区间涨幅 - 指数区间涨幅）
    # 例：10天涨110%、指数涨20% → 偏离 = 90%，不触发10日100%
    def _cum(n: int) -> Optional[float]:
        if len(s_closes) < n + 1:
            return None
        sr = s_closes[-1] / s_closes[-(n + 1)] - 1.0
        br = b_closes[-1] / b_closes[-(n + 1)] - 1.0
        return sr - br

    res.dev_3d = _cum(cfg.win_3d)
    res.dev_10d = _cum(cfg.win_10d)
    res.dev_30d = _cum(cfg.win_30d)
    res.stock_3d = _cum_stock(s_closes, cfg.win_3d)
    res.stock_10d = _cum_stock(s_closes, cfg.win_10d)
    res.stock_30d = _cum_stock(s_closes, cfg.win_30d)
    res.limitup_10d = _count_limitup(s_closes, limit, cfg.win_10d)
    res.limitup_30d = _count_limitup(s_closes, limit, cfg.win_30d)

    # ---- 触发判定（方向对称） ----
    d10, d30 = res.dev_10d, res.dev_30d

    if res.dev_3d is not None:
        res.normal_3d_triggered = abs(res.dev_3d) >= thr_3d - 1e-9

    if d10 is not None:
        res.serious_10d_up = d10 >= cfg.threshold_10d_up - 1e-9
        res.serious_10d_down = d10 <= cfg.threshold_10d_down + 1e-9
        res.headroom_10d_up = max(0.0, cfg.threshold_10d_up - d10)
        res.headroom_10d_down = max(0.0, d10 - cfg.threshold_10d_down)

    if d30 is not None:
        res.serious_30d_up = d30 >= cfg.threshold_30d_up - 1e-9
        res.serious_30d_down = d30 <= cfg.threshold_30d_down + 1e-9
        res.headroom_30d_up = max(0.0, cfg.threshold_30d_up - d30)
        res.headroom_30d_down = max(0.0, d30 - cfg.threshold_30d_down)

    # 接近判定：任一侧余量(相对该侧阈值幅度)不足 warn_margin
    res.near_serious = False
    if d10 is not None:
        up_margin = (cfg.threshold_10d_up - d10) / cfg.threshold_10d_up
        down_margin = (d10 - cfg.threshold_10d_down) / abs(cfg.threshold_10d_down)
        if d10 >= 0 and 0 <= up_margin <= cfg.warn_margin:
            res.near_serious = True
        if d10 < 0 and 0 <= down_margin <= cfg.warn_margin:
            res.near_serious = True
    if d30 is not None and not res.near_serious:
        up_margin = (cfg.threshold_30d_up - d30) / cfg.threshold_30d_up
        down_margin = (d30 - cfg.threshold_30d_down) / abs(cfg.threshold_30d_down)
        if d30 >= 0 and 0 <= up_margin <= cfg.warn_margin:
            res.near_serious = True
        if d30 < 0 and 0 <= down_margin <= cfg.warn_margin:
            res.near_serious = True

    # ---- 10日内同向普通异动计数 ----
    # 逐日滚动3日窗口(复合口径)偏离，统计最近 same_dir_days 个窗口触发同向的次数
    rolling3 = []
    for i in range(cfg.win_3d, len(common_dates)):
        sr = s_closes[i] / s_closes[i - cfg.win_3d] - 1.0
        br = b_closes[i] / b_closes[i - cfg.win_3d] - 1.0
        rolling3.append(sr - br)
    recent = rolling3[-cfg.same_dir_days:] if len(rolling3) > 0 else []
    res.same_dir_up_count = sum(1 for v in recent if v >= thr_3d)
    res.same_dir_down_count = sum(1 for v in recent if v <= -thr_3d)

    # ---- 备注 ----
    if res.serious_triggered:
        tags = []
        if res.serious_10d_up:
            tags.append("10日涨超+100%")
        if res.serious_10d_down:
            tags.append("10日跌超-50%")
        if res.serious_30d_up:
            tags.append("30日涨超+200%")
        if res.serious_30d_down:
            tags.append("30日跌超-70%")
        if res.same_dir_up_count >= 4:
            tags.append(f"10日{res.same_dir_up_count}次同向上行普通异动")
        if res.same_dir_down_count >= 4:
            tags.append(f"10日{res.same_dir_down_count}次同向下行普通异动")
        res.notes.append("触发严重异动(" + "/".join(tags) + ")：注意停牌/限制买入风险")
    elif res.normal_3d_triggered:
        direction = "上行" if (res.dev_3d or 0) >= 0 else "下行"
        res.notes.append(f"触发普通异动（3日{direction}偏离超阈值）")
    elif res.near_serious:
        res.notes.append("接近严重异动线，绕异动博弈区")
    return res
