# -*- coding: utf-8 -*-
"""决策动作矩阵 + 卖点规则库（P3）。quant/rules/actions.py

框架 v0.1 第5节：仓位 = f(周期阶段, 核心评分, 监管温度)
  | 周期 核心档 |  S(≥80)      | A(60-79)    | B/C(<60)      |
  | 启动 | 试仓 20-30%    | 观察新核心   | 空仓          |
  | 发酵 | 40-60%         | 20-30%       | 不做          |
  | 高潮 | 持有不加       | 兑现         | 空            |
  | 震荡 | ≤30% 高抛低吸  | 剔除         | 空            |
  | 退潮 | 只做冰点反包≤10% | 空          | 空仓          |
硬约束：监管温度≤−2 → 全线降半仓以下；严重异动高危区(余量<15%) → 尾盘兑现策略。

第6节卖点规则中可自动化的部分：
  R2 核心评分跌破60 → 减仓/兑现
  R5/R6 震荡期 冲高卖/跳水吸、高开兑现
  R7 带不动卖点：总核心封板但跟风冲高回落 → 次日冲高出
输出 ActionPlan（"今日该做什么"清单，人工执行）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from quant.indicators.core_score import CoreScore
from quant.regime.cycle import CycleState


# ---------- 动作矩阵（周期 x 评分档） ----------

# tier: "S" / "A" / "BC"
MATRIX = {
    "启动": {
        "S": ("试仓新核心(冰点反包) ", "20-30%", "冰点反转后的新题材领涨，小仓试错，错则次日走"),
        "A": ("观察候选核心", "≤10%", "地位未确认，轻仓跟踪或等发酵"),
        "BC": ("空仓", "0", "地位不足，不参与"),
    },
    "发酵": {
        "S": ("主攻·顺势做多", "40-60%", "总核心唯一主攻对象，分时低吸不追高"),
        "A": ("分支核心·可做", "20-30%", "做分支不碰中位，逻辑独立的才参与"),
        "BC": ("禁接力", "0", "中位股/补涨股最易A杀，禁止接力"),
    },
    "高潮": {
        "S": ("持有不加·只做总龙", "不加仓", "加速=买盘枯竭前夜，只持有最确定，尾盘异动先手出"),
        "A": ("兑现为主", "减仓", "中位跟风高潮期兑现，不追"),
        "BC": ("空", "0", "禁接力，高潮期接中位=接刀"),
    },
    "震荡": {
        "S": ("高抛低吸", "≤30%", "核心大涨卖/跳水吸，禁止追涨杀跌"),
        "A": ("核心低吸·不加", "≤15%", "只做核心回调低吸，不加仓"),
        "BC": ("空", "0", "震荡期不参与中低位，等方向选择"),
    },
    "退潮": {
        "S": ("冰点反包·试错", "≤10%", "亏钱效应衰竭后的反包/首板新核心，极小仓"),
        "A": ("空仓等待", "0", "退潮期不做接力"),
        "BC": ("空仓", "0", "空仓为主，等冰点反转信号"),
    },
}

# 周期基调（对应报告三节的操作基调，比 daily.py 内置的更细）
TONE = {
    "启动": "冰点反包/新题材首板试错期：盯第一个带动板块走强的核心，轻仓试错，做对加仓。",
    "发酵": "题材扩散主升期：围绕总核心+分支核心做多，分歧低吸，不追一致。",
    "高潮": "亢奋顶部区：只持有总龙不加仓；中位补涨/伪核心坚决不接力；异动余量<15%先手兑现。",
    "震荡": "赚钱效应钝化：核心高抛低吸、高开兑现，减少无效交易，等待方向选择。",
    "退潮": "亏钱效应扩散：空仓为主；仅冰点反转信号(溢价转正+首板批量)出现后小仓反包。",
}


def _tier(grade: str) -> str:
    return grade if grade in ("S", "A") else "BC"


def matrix_action(stage: str, grade: str) -> tuple:
    """动作矩阵查表 → (动作动词, 仓位区间, 说明)。未知 stage 归震荡。"""
    st = stage if stage in MATRIX else "震荡"
    return MATRIX[st][_tier(grade)]


# ---------- 输出结构 ----------

@dataclass
class StockAction:
    code: str
    name: str
    board_cnt: int
    grade: str
    total: float
    state: str
    verb: str = ""
    position: str = ""
    memo: str = ""
    risk_detail: str = ""


@dataclass
class ActionPlan:
    date: str = ""
    stage: str = ""
    tone: str = ""
    rules: list = field(default_factory=list)      # 全局纪律/硬约束(命中才列出)
    per_stock: list = field(default_factory=list)  # 每只高标动作
    watch: list = field(default_factory=list)      # 观察/人工确认项


# ---------- 主入口 ----------

def build_action_plan(
    cycle: CycleState,
    scores: list[CoreScore],
    *,
    date: str = "",
    reg_temp: float = 0.0,                 # 监管温度(人工事件输入,默认0)
    market_max_board: int = 0,
    lu_count: int = 0,
    zb_count: int = 0,
    holdings: Optional[list] = None,       # 持仓 [{code,name}]
) -> ActionPlan:
    """由周期状态 + 核心评分卡清单 → 交易动作计划。"""
    plan = ActionPlan(date=date, stage=cycle.stage, tone=TONE.get(cycle.stage, ""))

    # ---------- 全局硬约束 / 纪律 ----------
    if reg_temp <= -2:
        plan.rules.append(f"⚠️ 监管温度 {reg_temp:.0f} ≤ −2：全线降半仓以下，高位核心只出不进")
    if reg_temp <= -1:
        plan.rules.append(f"监管温度 {reg_temp:.0f}：注意停牌/限制买入类公告，持仓异动股控制风险")

    # 总龙带不动检测（规则7代理）：最高分S核心存在但板块跟风弱/炸板多
    s_core = next((s for s in scores if s.grade == "S"), None)
    if s_core is not None and (zb_count >= 12 or lu_count <= 30):
        plan.rules.append(
            f"🔔 规则7·带不动预警：总核心 {s_core.name} 封板但跟风不足"
            f"(涨停{lu_count}/炸板{zb_count})，若持有：次日冲高先兑现，防低开")

    if cycle.stage == "震荡":
        plan.rules.append("规则5/6·震荡纪律：冲高卖、跳水吸、利好高开兑现，禁止追涨杀跌")
    if cycle.stage == "退潮":
        plan.rules.append("规则9·走势参考：退潮期高度逐级衰减，反包前不接中位")
    if cycle.stage == "高潮":
        plan.rules.append("高潮期严禁接力中位/补涨；盯严重异动公告，异动余量<15%的持仓尾盘兑现")

    # ---------- 每只高标：矩阵动作 + 卖点规则修正 ----------
    holdings = holdings or []
    hold_codes = {h["code"] for h in holdings}

    for s in sorted(scores, key=lambda x: x.total, reverse=True):
        verb, pos, memo = matrix_action(cycle.stage, s.grade)
        extra = []

        # 状态机覆盖（比矩阵更严格的场景优先）
        if s.state == "伪核心·禁接力":
            verb, pos = "禁接力", "0"
            extra.append("中位一字大面源泉，不参与")
        elif s.state == "监管高危(结束预警)":
            verb, pos = "规避/清仓", "0"
            extra.append("已触发严重异动，回避停牌/限制买入风险")
        elif s.state == "走弱(减/剔)":
            verb, pos = "减/剔除", "持仓减半以上"
            extra.append("连续低开不创新高，地位走弱")
        # 异动体检高危（未到严重，但余量<15%）
        if s.dev is not None and s.dev.risk_level == "高危接近" and verb not in ("规避/清仓",):
            extra.append(f"距严重异动线近(10日偏离{s.dev.dev_10d*100:+.0f}%)，尾盘兑现策略启动")

        # 卖点规则 R2：持仓且评分跌破 60 → 减/兑现
        if s.code in hold_codes and s.grade in ("B", "C"):
            verb, pos = "减仓/兑现", "降半仓"
            extra.append(f"规则2·核心评分{s.total:.0f}<60，跌破核心线")
        if s.code in hold_codes and s.grade == "A" and cycle.stage == "高潮":
            verb, pos = "兑现", "降半仓"
            extra.append("规则2·高潮期A级核心兑现")

        plan.per_stock.append(StockAction(
            code=s.code, name=s.name, board_cnt=s.board_cnt,
            grade=s.grade, total=s.total, state=s.state,
            verb=verb, position=pos,
            memo=(memo + ("；" + "；".join(extra) if extra else "")),
            risk_detail=s.risk_detail,
        ))

    # ---------- 观察清单（人工确认项） ----------
    # 逻辑强度缺省 4 分是主要压分项：B/A 级候选若人工确认题材为业绩/政策级，
    # 把 logic 从 4 上调到 8 预估可升 A/S 级 → 变成可操作对象。
    for s in sorted(scores, key=lambda x: x.total, reverse=True):
        if s.grade not in ("A", "B") or s.b_logic >= 8.0:
            continue
        boost = 8.0
        est = s.total + (boost - s.b_logic) / 0.7   # 0.7 = 70正向分映射到100
        how = "可升A级参与" if est >= 60 else ("接近A级" if est >= 55 else "仍不足参与")
        plan.watch.append(
            f"{s.name} {s.grade}级({s.total:.0f}分)：逻辑强度当前按缺省{s.b_logic:.0f}/10 计，"
            f"人工确认为业绩/政策级并上调至 {boost:.0f} 后预估 {est:.0f} 分，{how}（纯情绪则维持禁接力）")
    return plan


# ---------- 展示 ----------

def render(plan: ActionPlan) -> str:
    L = [f"📋 今日操作清单 {plan.date}（周期：{plan.stage}）",
         f"基调：{plan.tone}", ""]
    if plan.rules:
        L.append("【全局纪律/硬约束】")
        L += [f"- {r}" for r in plan.rules]
        L.append("")
    L.append("【高标动作】")
    L.append("| 标的 | 高度 | 评分 | 等级 | 状态 | 动作 | 仓位 |")
    L.append("|---|---|---|---|---|---|---|")
    for a in plan.per_stock:
        L.append(f"| {a.name} | {a.board_cnt}板 | {a.total:.0f} | {a.grade} | {a.state} "
                 f"| {a.verb} | {a.position} |")
    L.append("")
    if plan.watch:
        L.append("【需人工确认】")
        L += [f"- {w}" for w in plan.watch]
    return "\n".join(L)
