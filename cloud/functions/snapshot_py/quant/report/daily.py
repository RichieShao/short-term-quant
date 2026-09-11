# -*- coding: utf-8 -*-
"""每日盘后报告生成器（P2 + P3）。quant/report/daily.py

报告组成：
  1. 大盘环境（三大指数收盘涨跌）
  2. 情绪温度计（今日 + 近5日序列）
  3. 周期阶段判定（regime/cycle）
  4. 题材热度 + 高标梯队
  5. 高标梯队：核心评分卡 + 异动体检（P1+P3）
  6. 今日操作清单（动作矩阵 + 卖点规则，P3）
  7. 风险提示

用法见 ../report_daily.py（项目根 CLI）。
"""
from __future__ import annotations

import datetime as _dt

from quant.data.kline import fetch_daily, fetch_realtime, prev_trade_date
from quant.data.pools import fetch_zt_pool
from quant.indicators.abnormal import compute_deviation
from quant.indicators.core_score import score_core
from quant.indicators.sentiment import compute_sentiment, heat_score
from quant.regime.cycle import classify
from quant.rules.actions import build_action_plan


INDEXES = [
    ("sh000001", "上证指数"),
    ("sz399001", "深证成指"),
    ("sz399006", "创业板指"),
]


def _trade_dates(n: int) -> list[str]:
    """最近n个交易日（升序），以上证日K为准。"""
    rows, _ = fetch_daily("sh000001", count=n + 10)
    return [r["date"] for r in rows][-n:]


def market_env(date: str | None = None) -> str:
    """三大指数当日涨跌。date 指定则按日K取当日涨跌幅（历史回看准确），否则用实时。"""
    if date:
        parts = []
        for c, nm in INDEXES:
            try:
                rows, _ = fetch_daily(c, count=8)
                ds = [r["date"] for r in rows]
                if date in ds:
                    i = ds.index(date)
                    pct = rows[i]["close"] / rows[i - 1]["close"] - 1.0 if i >= 1 else 0.0
                    arrow = "🔴" if pct >= 0 else "🟢"
                    parts.append(f"{nm} {arrow}{pct*100:+.2f}%")
            except Exception:
                continue
        return " | ".join(parts) if parts else "指数数据不可用"
    rt = fetch_realtime([c for c, _ in INDEXES])
    parts = []
    for c, nm in INDEXES:
        v = rt.get(c)
        if v:
            arrow = "🔴" if v["pct"] >= 0 else "🟢"
            parts.append(f"{nm} {arrow}{v['pct']*100:+.2f}%")
    return " | ".join(parts)


def sentiment_series(dates: list[str]) -> list:
    """近N日情绪序列。

    注：隔日溢价用实时行情推算，只对最新交易日有效；
    历史日的溢价需次日收盘价计算(成本高)，暂标记为 None，趋势列不受影响。
    """
    out = []
    for i, d in enumerate(dates):
        need_prem = (i == len(dates) - 1)
        out.append(compute_sentiment(date=d, need_premium=need_prem))
    return out


def markdown_table(rows, headers):
    """简版 markdown 表格渲染（转义|）。"""
    hdr = "| " + " | ".join(headers) + " |"
    sep = "|" + "---|" * len(headers)
    lines = [hdr, sep]
    for r in rows:
        cells = [str(c).replace("|", "\\|") for c in r]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_report(date: str | None = None) -> str:
    if date is None:
        dates = _trade_dates(6)
        today = dates[-1]
    else:
        dates = _trade_dates(8)
        dates = [d for d in dates if d <= date][-6:]
        today = dates[-1] if dates else date

    env = market_env(today)
    series = sentiment_series(dates)
    cur: object = series[-1]
    cyc = classify(cur, series[-2] if len(series) >= 2 else None)

    # ---- 高标体检 + 核心评分（P3）：连板>=2 高度前10 ----
    leaders = sorted(
        (x for x in cur.leaders if x["board"] >= 2),
        key=lambda d: d["board"], reverse=True)[:10]

    # 当日/昨日涨停池（核心评分用：行业带动、梯队、带动性衰减）
    zt_today = []
    prev_zt = []
    try:
        zt_today = fetch_zt_pool(today.replace("-", ""))
        idx_rows, _ = fetch_daily("sh000001", count=30)
        yday = prev_trade_date(idx_rows, asof=today)
        if yday:
            prev_zt = fetch_zt_pool(yday.replace("-", ""))
    except Exception:
        pass

    # 基准行缓存
    bench_cache: dict[str, tuple] = {}

    def analyze_leader(ld: dict) -> tuple:
        """一次拉取：异动体检(dev) + 核心评分(sc)。网络失败时降级返回。
        cur.leaders 字段不全(board/无首封)，用当日涨停池完整元素补全。"""
        from quant.data.kline import benchmark_index, normalize_code
        src = next((x for x in zt_today if x["code"] == ld["code"]), None)
        ld = src or ld            # 完整元素含 board_cnt/first_seal/zhaban_cnt
        code = normalize_code(ld["code"])
        bcode = benchmark_index(code)
        if bcode not in bench_cache:
            bench_cache[bcode] = fetch_daily(bcode, count=80)
        try:
            stock_rows, name = fetch_daily(code, count=80)
        except Exception:
            return None, None
        br, _bn = bench_cache[bcode]
        dev = None
        try:
            dev = compute_deviation(stock_rows, br, code, name=ld["name"],
                                    bench_code=bcode, bench_name=_bn or bcode)
        except Exception:
            dev = None
        try:
            sc = score_core(ld, zt_today, stock_rows,
                            market_max_board=cur.max_board,
                            stage=cyc.stage, heat=cur.heat,
                            prev_zt=prev_zt or None, dev=dev)
        except Exception:
            sc = None
        return dev, sc

    analyzed = [(ld, *analyze_leader(ld)) for ld in leaders]  # (ld, dev, sc)
    valid_scores = [sc for _, _d, sc in analyzed if sc is not None]

    # ---- 组装报告 ----
    L = []
    L.append(f"# 短线情绪盘后报告 {today}\n")
    L.append(f"> 情绪温度计 × 周期定位 × 核心评分 × 异动体检 | 框架 v0.1-P4 | 生成于 {_dt.datetime.now():%Y-%m-%d %H:%M}\n")
    L.append("---\n")
    L.append(f"## 一、大盘环境\n\n{env}\n")

    L.append("\n## 二、情绪温度计（近6个交易日）\n")
    rows = []
    for s in series:
        rows.append([
            s.date, f"{s.heat:.0f}", s.band, s.lu_count, s.ld_count,
            s.zb_count, f"{s.zhaban_rate*100:.0f}%" if s.zhaban_rate is not None else "—",
            f"{s.max_board}板", s.conn_board_count,
            f"{s.yest_premium*100:+.1f}%" if s.yest_premium is not None else "—",
        ])
    L.append(markdown_table(rows, ["日期", "温度", "档位", "涨停", "跌停", "炸板", "炸板率", "最高板", "连板家数", "昨涨停溢价"]))
    L.append(f"\n> 说明：情绪温度分0-100（涨停40/高度20/连板15/炸板率10/溢价15，跌停-20修正）。刻度与分档已于 P4(2026-09-02) 按 2025-08~2026-09 一年回放校准，见 sentiment.py/cycle.py 注释。\n")

    L.append("\n## 三、周期阶段判定\n")
    L.append(f"**{cyc.stage}**（趋势：{cyc.trend or '单日'}）\n")
    for r in cyc.reason:
        L.append(f"- {r}")
    L.append("")
    op = {
        "启动": "试仓低位新核心，冰点反包首板重点跟踪",
        "发酵": "围绕题材核心/分支核心做多，分歧低吸",
        "高潮": "只做总龙不加仓，中位补涨坚决不接力，盯监管动作",
        "震荡": "核心高抛低吸，等待方向选择，减少无效交易",
        "退潮": "空仓为主，等待亏钱效应衰竭后的冰点反转信号",
    }.get(cyc.stage, "")
    if op:
        L.append(f"- **操作基调**：{op}\n")

    L.append("\n## 四、题材热度 TOP5\n")
    ind_rows = [[i, n, f"{m}板"] for i, n, m in cur.top_industries[:5]]
    L.append(markdown_table(ind_rows, ["题材", "涨停家数", "板块最高"]))
    L.append("\n> 题材=东财行业分类；更细的概念/题材归并见 P4。\n")

    # ---- 第五节：核心评分 + 异动体检 ----
    L.append("\n## 五、高标梯队：核心评分与异动体检\n")
    if valid_scores:
        sc_rows = []
        for ld, dev, sc in analyzed:
            if sc is None:
                continue
            flag = {"严重异动": "🚨", "高危接近": "🔶"}.get(
                sc.dev.risk_level if sc.dev else "", "")
            head = ""
            if sc.dev is not None and sc.dev.dev_30d is not None:
                if sc.dev.serious_30d_up:
                    head = "已触"
                elif sc.dev.dev_30d > 0:
                    head = f"余{sc.dev.headroom_30d_up*100:.0f}pp"
            sc_rows.append([
                f"{sc.name}({sc.code[2:]})", f"{sc.board_cnt}板",
                f"{sc.total:.0f}", sc.grade, sc.state,
                f"{sc.sub_a:.0f}", f"{sc.sub_b:.0f}", f"-{sc.risk_total:.0f}",
                f"{sc.dev.dev_10d*100:+.0f}%" if sc.dev and sc.dev.dev_10d is not None else "—",
                f"{sc.dev.dev_30d*100:+.0f}%" if sc.dev and sc.dev.dev_30d is not None else "—",
                head, flag,
            ])
        L.append(markdown_table(sc_rows, ["标的", "高度", "总分", "档", "状态", "A地位/40", "B持续/30", "风险", "10日偏离", "30日偏离", "30日线", "异动"]))
        L.append("\n连板天梯（全市场）: ")
        L.append("  ".join(f"{k}板×{v}" for k, v in sorted(cur.ladder.items()) if v))
        L.append("")
        L.append("> 总分=带动性+持续性−风险(0-100)：S≥80/A≥60/B≥45/C<45。A地位=板块带动+首封时序+人气+被动性；"
                 "B持续=梯队+节点+逻辑(缺省4/10需人工确认)；风险=一字断层/中位一字/连续低开/失去带动/严重异动。"
                 "异动列：🚨=严重(10日+100%/-50%、30日+200%/-70%) | 🔶=接近严重线 | 空=普通异动属连板常态。")
        L.append("")
    else:
        L.append("（核心评分失败：涨停池/日K数据不可用）\n")

    # ---- 第六节：今日操作清单（P3 动作矩阵） ----
    L.append("\n## 六、今日操作清单\n")
    if valid_scores:
        try:
            plan = build_action_plan(
                cyc, valid_scores, date=today,
                market_max_board=cur.max_board,
                lu_count=cur.lu_count, zb_count=cur.zb_count)
            L.append(f"**周期 {plan.stage}** 基调：{plan.tone}\n")
            if plan.rules:
                L.append("**全局纪律/硬约束**")
                L += [f"- {r}" for r in plan.rules]
                L.append("")
            L.append("**高标动作**")
            pa_rows = [[a.name, f"{a.board_cnt}板", f"{a.total:.0f}", a.grade,
                        a.state, a.verb, a.position] for a in plan.per_stock]
            L.append(markdown_table(pa_rows, ["标的", "高度", "评分", "档", "状态", "动作", "仓位"]))
            L.append("")
            flagged = [a for a in plan.per_stock
                       if a.verb in ("禁接力", "规避/清仓", "减/剔除", "减仓/兑现")
                       or a.grade == "C"]
            for a in flagged:
                L.append(f"- **{a.name}**（{a.total:.0f}分 {a.grade}·{a.state}）：{a.verb}（仓位{a.position}）。{a.memo}")
            if plan.watch:
                L.append("\n**需人工确认（逻辑强度标注）**")
                L += [f"- {w}" for w in plan.watch]
            L.append("")
        except Exception as e:
            L.append(f"（动作矩阵生成失败：{e}）\n")
    else:
        L.append("无有效评分数据，跳过动作清单。\n")

    L.append("\n## 七、风险提示\n")
    L.append("- 本报告为量化规则输出，非投资建议；监管动作（停牌/限制买入等）无公开数据源，需人工结合公告。\n- 核心评分中带动性/主动性用涨停池+日K代理，分时联动、龙虎榜人气、题材逻辑需人工复核（见框架文档第8节已知边界）。\n- 阈值均为经验初值，待 P4 历史回测校准。\n")
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else None
    print(build_report(date))
