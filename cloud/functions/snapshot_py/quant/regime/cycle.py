# -*- coding: utf-8 -*-
"""周期阶段判定（P2）。quant/regime/cycle.py

将《个人关于投机的理解与做法》"启动-发酵-高潮-震荡-退潮"映射到情绪温度计指标。
纯规则启发式，阈值集中于此，P4 用历史题材周期回测校准。

判定依据(每日)：
  启动：涨停家数从低位回升、高度初现(2-3板)、温度从冰点爬升
  发酵：温度>=56、连板家数扩张、题材扩散、隔日溢价转正
  高潮：温度>=66 或 高度>=11板 且 涨停家数拥挤；"加速=买盘枯竭前夜"
  震荡：温度中位但赚钱效应钝化（炸板率高、溢价走弱、高标卡位轮动）
  退潮：温度<33 或 跌停放大、溢价转负、高度崩塌
（周期线为 P4 校准后数值，详见 CycleConfig 注释；阈值集中于此，可持续回测迭代）
"""
from __future__ import annotations

from dataclasses import dataclass, field

from quant.indicators.sentiment import DailySentiment


# ---------- 阈值配置（P4 校准对象） ----------

@dataclass
class CycleConfig:
    # 周期线 = 温度绝对阈值。2026-09-02 P4 用 2025-08~2026-09 全年回放校准：
    # 旧线 72/55/32 按温度计旧刻度(70/6/25)标定，该刻度在新市场生态下饱和（涨停常80-150），
    # 导致周期 75% 日子判"高潮"、全年零"退潮"。新刻度(100/13/28)下温度 p50≈56，
    # 新线取 高潮≈p75(66)、发酵≈p50(56)、启动≈p18(48)、冰点≈p2(33)；在线含炸板率/溢价/跌停，
    # 实际温度更高，高潮线可达性更强、退潮靠跌停放大+溢价转负路径（ld_heavy）触发。
    heat_high: float = 66.0      # >= 高潮区
    heat_warm: float = 56.0      # >= 发酵区
    heat_cold: float = 33.0      # <  退潮区
    heat_launch: float = 48.0    # 启动区下限(配合趋势)
    board_high: int = 11         # 高度>=11板 → 高潮参考（原6板在新生态下 89% 日子满足，失效）
    lu_high: int = 90            # 涨停家数>=90 → 拥挤（原70同因失效）
    lu_low: int = 25             # 涨停<25 → 冰点倾向
    conn_high: int = 20          # 连板家数>=20 → 题材扩散强
    zhaban_rate_high: float = 0.35  # 炸板率>35% → 分歧/退潮
    premium_neg: float = -0.01   # 隔日溢价< -1% → 亏钱效应
    premium_pos: float = 0.02    # 隔日溢价> +2% → 赚钱效应


DEFAULT_CC = CycleConfig()


@dataclass
class CycleState:
    stage: str                    # 启动/发酵/高潮/震荡/退潮
    reason: list = field(default_factory=list)
    trend: str = ""               # 较前一日：回升/回落/持平


def _trend(cur: DailySentiment, prev: DailySentiment | None) -> str:
    if prev is None:
        return ""
    d = cur.heat - prev.heat
    if d >= 5:
        return "回升"
    if d <= -5:
        return "回落"
    # 涨停家数方向兜底
    if cur.lu_count - prev.lu_count >= 10:
        return "回升"
    if cur.lu_count - prev.lu_count <= -10:
        return "回落"
    return "持平"


def classify(cur: DailySentiment, prev: DailySentiment | None = None,
             cfg: CycleConfig = DEFAULT_CC) -> CycleState:
    """单日 + 前一日趋势 → 周期阶段。"""
    cs = CycleState(stage="震荡", reason=[])
    cs.trend = _trend(cur, prev)

    lu, ld = cur.lu_count, cur.ld_count
    heat = cur.heat
    mb = cur.max_board
    zb_rate = cur.zhaban_rate or 0.0
    prem = cur.yest_premium
    conn = cur.conn_board_count

    # 跌停压制：跌停明显多于常态(>=15)且溢价为负
    ld_heavy = ld >= 15 and (prem is not None and prem < cfg.premium_neg)

    # ---- 退潮 ----
    if heat < cfg.heat_cold or ld_heavy or lu < cfg.lu_low and prem is not None and prem < cfg.premium_neg:
        cs.stage = "退潮"
        cs.reason.append(f"温度{heat:.0f}冰点/涨停{lu}家萎缩/跌停{ld}家放大")
        cs.reason.append("空仓为主，只做冰点反包/首板试错（若溢价转正）")
        return cs

    # ---- 高潮 ----
    if heat >= cfg.heat_high or (mb >= cfg.board_high and lu >= cfg.lu_high * 0.7):
        cs.stage = "高潮"
        cs.reason.append(f"温度{heat:.0f}亢奋，高度{mb}板/涨停{lu}家")
        cs.reason.append("加速=买盘枯竭前夜：只做最确定总龙，不追中位补涨，警惕监管")
        return cs

    # ---- 发酵（排除"回落"趋势：高位回落后不算扩散） ----
    if heat >= cfg.heat_warm and zb_rate < cfg.zhaban_rate_high and (
            prem is None or prem >= cfg.premium_neg) and cs.trend != "回落":
        cs.stage = "发酵"
        cs.reason.append(f"温度{heat:.0f}活跃且趋势{cs.trend or '平稳'}，连板{conn}家/炸板率{zb_rate*100:.0f}%")
        cs.reason.append("题材扩散期：做核心/分支核心，分歧低吸")
        return cs

    # ---- 高潮后大幅降温 → 震荡(退潮预警) ----
    if prev is not None and prev.heat >= cfg.heat_high and cur.heat <= prev.heat - 12:
        cs.stage = "震荡"
        cs.reason.append(f"高潮({prev.heat:.0f})后骤降至{heat:.0f}，属退潮预警窗口")
        cs.reason.append("降低仓位，防A杀；只做核心低吸，等亏钱效应确认再空仓")
        return cs

    # ---- 启动（温度中位以下回升或低基数起步） ----
    if cs.trend == "回升" and heat >= cfg.heat_launch and mb >= 2:
        cs.stage = "启动"
        cs.reason.append(f"温度{heat:.0f}回升(前{prev.heat:.0f})，高度{mb}板起步")
        cs.reason.append("情绪冰点后反包/首板高溢价，试仓新核心")
        return cs

    # ---- 震荡 ----
    cs.stage = "震荡"
    cs.reason.append(
        f"温度{heat:.0f}中位但赚钱效应钝化(炸板率{zb_rate*100:.0f}%"
        + (f"/溢价{prem*100:+.1f}%)" if prem is not None else ")"))
    cs.reason.append("核心高抛低吸，不做中位接力；等方向选择")
    return cs


def classify_series(series: list[DailySentiment], cfg: CycleConfig = DEFAULT_CC) -> CycleState:
    """多日序列：取最后一日 + 前一日判定。series 升序。"""
    if not series:
        raise ValueError("空序列")
    cur = series[-1]
    prev = series[-2] if len(series) >= 2 else None
    return classify(cur, prev, cfg)
