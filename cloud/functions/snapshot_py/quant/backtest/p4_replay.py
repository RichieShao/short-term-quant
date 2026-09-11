# -*- coding: utf-8 -*-
"""P4 回测数据管线二：逐日回放 温度计×周期 + 转折点命中率自评。

数据：.workbuddy/p4/zt/*.json（同花顺涨停池，仅 ZT；无跌停/炸板历史源）
口径说明（诚实降级）：
  - 炸板池缺 → heat 的炸板率 10 分项不参与；跌停池缺 → 跌停惩罚 0
  - 隔日溢价历史不可算（实时行情只对当日）→ prem=None 给中值 +7.5
  - 故本回放 heat 上限 ~82.5（在线口径上限 92.5），阈值比较在同一窗口内自洽

评估方法（自洽性回归，标签来自同一 lu/heat 序列，有内在循环性——文档中明示）：
  1. 高潮顶点日：lu 为 ±2/+3 局部峰 且 lu>=55 且 3 日内跌幅 >=30%
  2. 退潮兑现日：顶点后 c+1..c+5 内首个 lu <= 0.7*顶点 lu 的日子
  3. 命中判定：顶点日 classify==高潮(严格)/∈{高潮,发酵}(宽松)；
             退潮兑现日 classify∈{震荡,退潮}
用法：
  python3 -m quant.backtest.p4_replay [--start 2025-08-18] [--end 2026-09-02] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from quant.backtest.p4_ths_pool import CACHE, load_cached, trade_dates  # noqa: E402
from quant.backtest.theme_life import _TAG_STOP, _tags_of  # noqa: E402  标签口径唯一来源(theme_life)
from quant.indicators.sentiment import compute_sentiment_from_pools, DEFAULT_SC  # noqa: E402
from quant.regime.cycle import classify, DEFAULT_CC, CycleConfig  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".workbuddy", "p4")
OUT_DIR = os.path.abspath(OUT_DIR)


def load_series(start: str, end: str, cfg=DEFAULT_SC):
    """返回 (dates, sentiments, zt_list)。zt_list 供题材主题分析。"""
    dates = [d for d in trade_dates(start, end)]
    series, zts = [], []
    for d in dates:
        rows = load_cached(d) or []
        s = compute_sentiment_from_pools(d, rows, dt=[], zb=[], yest_premium=None, cfg=cfg)
        series.append(s)
        zts.append((d, rows))
    return dates, series, zts


def replay(start: str, end: str, cc: CycleConfig = DEFAULT_CC, sc: "object" = DEFAULT_SC):
    """逐日 classify，返回 [(sentiment, cycle_state)]。"""
    dates, series, _ = load_series(start, end, sc)
    out = []
    for i, s in enumerate(series):
        prev = series[i - 1] if i >= 1 else None
        out.append((s, classify(s, prev, cc)))
    return out


# ---------- 自评标签 ----------

def find_turning_points(series: list, lu_min: int | None = None) -> dict:
    """返回 {climaxes: [(i,date,lu,heat)], retreats: [(i,date,lu)], troughs: [(i,date,lu)]}
    高潮顶点口径（2026-09-02 校准后）：lu 为 ±2/+3 局部峰、lu >= max(lu_floor, p75)，
    且 3 日内回落 >=30%（强高潮，避免把中位日当顶点）。lu_min 缺省取序列 p75 自适应。
    """
    lu = [s.lu_count for s in series]
    heat = [s.heat for s in series]
    n = len(series)
    if lu_min is None:
        sl = sorted(lu)
        lu_min = sl[min(n - 1, int(n * 0.75))]
    climaxes, retreats, troughs = [], [], []
    # 高潮顶点
    for i in range(n):
        if lu[i] < lu_min:
            continue
        if any(lu[j] > lu[i] for j in range(max(0, i - 2), i)):
            continue
        fwd = range(i + 1, min(n, i + 4))
        if not any(lu[j] <= 0.7 * lu[i] for j in fwd):
            continue
        climaxes.append((i, series[i].date, lu[i], heat[i]))
    # 退潮兑现日：每个顶点后首个 lu<=0.7*顶点lu
    for (i, date, lu_i, _h) in climaxes:
        for j in range(i + 1, min(n, i + 6)):
            if lu[j] <= 0.7 * lu_i:
                retreats.append((j, series[j].date, lu[j]))
                break
    # 冰点谷底：lu<=30 且 3 日内反弹 >=50%
    for i in range(n):
        if lu[i] > 30:
            continue
        fwd = [lu[j] for j in range(i + 1, min(n, i + 4))]
        if fwd and max(fwd) >= 1.5 * lu[i]:
            troughs.append((i, series[i].date, lu[i]))
    return {"climaxes": climaxes, "retreats": retreats, "troughs": troughs}


def evaluate(series: list, states: list, tp: dict) -> dict:
    """命中统计。"""
    stages = [c.stage for c in states]
    res = {"climax_total": 0, "climax_hit_strict": 0, "climax_hit_loose": 0,
           "retreat_total": 0, "retreat_hit": 0, "trough_total": 0,
           "trough_rebound_stages": {}}
    res["climax_total"] = len(tp["climaxes"])
    for i, *_ in tp["climaxes"]:
        st = stages[i]
        if st == "高潮":
            res["climax_hit_strict"] += 1
        if st in ("高潮", "发酵"):
            res["climax_hit_loose"] += 1
    res["retreat_total"] = len(tp["retreats"])
    for i, *_ in tp["retreats"]:
        # 退潮兑现日或其后 1 日内
        st = stages[i]
        st2 = stages[i + 1] if i + 1 < len(series) else ""
        if st in ("震荡", "退潮") or st2 in ("震荡", "退潮"):
            res["retreat_hit"] += 1
    res["trough_total"] = len(tp["troughs"])
    for i, *_ in tp["troughs"]:
        # 反弹日（3 日内首次 >=1.5x）
        lu = [s.lu_count for s in series]
        for j in range(i + 1, min(len(series), i + 4)):
            if lu[j] >= 1.5 * lu[i]:
                res["trough_rebound_stages"][stages[j]] = res["trough_rebound_stages"].get(stages[j], 0) + 1
                break
    return res


def render_table(series, states) -> str:
    hdr = "| 日期 | 涨停 | 最高板 | 梯队(≥2板) | 温度 | 档位 | 周期 | 趋势 | 题材TOP2 |"
    sep = "|" + "---|" * 9
    lines = [hdr, sep]
    for s, c in zip(series, states):
        th = "、".join(f"{i}({n}家/{m}板)" for i, n, m in s.top_industries[:2])
        lines.append(f"| {s.date} | {s.lu_count} | {s.max_board}板 | {s.conn_board_count} | "
                     f"{s.heat:.0f} | {s.band} | **{c.stage}** | {c.trend or '单日'} | {th} |")
    return "\n".join(lines)


def theme_cycles(zts: list, top_n: int = 12):
    """按 reason 标签聚合成日序列，输出峰值最高的主题。"""
    days = [d for d, _ in zts]
    tags = {d: {} for d, _ in zts}
    for d, rows in zts:
        for r in rows:
            for t in _tags_of(r.get("reason", "")):
                tags[d][t] = tags[d].get(t, 0) + 1
    # 主题生命期
    agg = {}
    for d, m in tags.items():
        for t, c in m.items():
            a = agg.setdefault(t, {"dates": [], "counts": [], "peak": 0})
            a["dates"].append(d)
            a["counts"].append(c)
            a["peak"] = max(a["peak"], c)
    top = sorted(agg.items(), key=lambda kv: kv[1]["peak"], reverse=True)[:top_n]
    return top, days, tags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-08-18")
    ap.add_argument("--end", default="2026-09-02")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)

    dates, series, zts = load_series(args.start, args.end)
    states = []
    for i, s in enumerate(series):
        prev = series[i - 1] if i >= 1 else None
        states.append(classify(s, prev))
    tp = find_turning_points(series)
    ev = evaluate(series, states, tp)
    ev["window"] = [args.start, args.end, len(series)]

    # 表格
    tbl = render_table(series, states)
    with open(os.path.join(OUT_DIR, "replay_table.md"), "w", encoding="utf-8") as f:
        f.write(tbl + "\n")
    # 命中 csv
    import csv as _csv
    with open(os.path.join(OUT_DIR, "evaluate.csv"), "w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow(["指标", "值"])
        for k, v in ev.items():
            w.writerow([k, v if not isinstance(v, dict) else json.dumps(v, ensure_ascii=False)])
    # 主题周期
    top, days, tags = theme_cycles(zts, top_n=15)
    theme_path = os.path.join(OUT_DIR, "themes_top.md")
    with open(theme_path, "w", encoding="utf-8") as f:
        f.write("| 主题 | 峰值日家数 | 出现交易日 | 生命期(首尾) |\n")
        f.write("|" + "---|" * 4 + "\n")
        for t, a in top:
            f.write(f"| {t} | {a['peak']} | {len(a['dates'])} | {a['dates'][0]} ~ {a['dates'][-1]} |\n")

    if args.json:
        print(json.dumps(ev, ensure_ascii=False, indent=1))
    else:
        n = len(series)
        print(f"窗口 {args.start}~{args.end}：{n} 个交易日")
        print(f"高潮顶点 {ev['climax_total']} 个 → 严格命中(高潮) {ev['climax_hit_strict']} "
              f"({100*ev['climax_hit_strict']/max(1,ev['climax_total']):.0f}%) | "
              f"宽松命中(高潮/发酵) {ev['climax_hit_loose']} "
              f"({100*ev['climax_hit_loose']/max(1,ev['climax_total']):.0f}%)")
        print(f"退潮兑现 {ev['retreat_total']} 个 → 命中(震荡/退潮) {ev['retreat_hit']} "
              f"({100*ev['retreat_hit']/max(1,ev['retreat_total']):.0f}%)")
        print(f"冰点谷底 {ev['trough_total']} 个 → 反弹日周期分布 {ev['trough_rebound_stages']}")
        print(f"\n表格已存 {os.path.join(OUT_DIR,'replay_table.md')}；主题TOP15 {theme_path}")
        # 关键转折点摘要
        print("\n--- 转折点明细 ---")
        for kind, arr in (("高潮顶点", tp["climaxes"]), ("退潮兑现", tp["retreats"])):
            for i, d, lu in [(i, dt_, lu_) for i, dt_, lu_, *_ in arr]:
                print(f"  {kind} {d} 涨停{lu}")


if __name__ == "__main__":
    main()
