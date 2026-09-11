# -*- coding: utf-8 -*-
"""P4 校准实验：在 1 年窗口内搜索 温度计刻度/周期阈值 候选并评估。

评估口径（与 p4_replay 一致的自洽性回归）：
  climax 顶点日 = lu±2/+3 局部峰、lu>=55、3 日内回落>=30%
  retreat 兑现日 = 顶点后 5 日内首个 lu<=0.7*顶点lu
  命中：climax 日 classify==高潮(严格)；retreat 日或次日 classify∈{震荡,退潮}
候选生成：
  刻度(lu/board/ladder scale) 取分布分位锚点（p85/p90 附近），循环线取自身
  heat 分布分位数，另加人工备选；全部做交叉指标输出，人工选定。
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from quant.backtest.p4_replay import load_series, find_turning_points, evaluate  # noqa: E402
from quant.indicators.sentiment import SentimentConfig, compute_sentiment_from_pools  # noqa: E402
from quant.regime.cycle import CycleConfig, classify  # noqa: E402


def pct(a, p):
    a = sorted(a)
    return a[min(len(a) - 1, int(len(a) * p))]


def build_series_with(rows_by_date, dates, sc_cfg):
    out = []
    for d in dates:
        s = compute_sentiment_from_pools(d, rows_by_date[d], dt=[], zb=[],
                                         yest_premium=None, cfg=sc_cfg)
        out.append(s)
    return out


def eval_config(dates, series, cc, tag=""):
    states = []
    for i, s in enumerate(series):
        prev = series[i - 1] if i >= 1 else None
        states.append(classify(s, prev, cc))
    tp = find_turning_points(series)
    ev = evaluate(series, states, tp)
    stage_c = Counter(c.stage for c in states)
    heat_vals = sorted(s.heat for s in series)
    n = len(series)
    climax_strict_pct = 100 * ev["climax_hit_strict"] / max(1, ev["climax_total"])
    retreat_pct = 100 * ev["retreat_hit"] / max(1, ev["retreat_total"])
    hi_share = 100 * stage_c["高潮"] / n
    print(f"[{tag}] 高潮命中 {climax_strict_pct:.0f}% | 退潮命中 {retreat_pct:.0f}% "
          f"| 周期 {dict(stage_c)} "
          f"| 温度p10={pct(heat_vals,.1):.0f} p50={pct(heat_vals,.5):.0f} p90={pct(heat_vals,.9):.0f}")
    return {"ev": ev, "cc": cc, "stage": stage_c, "hi_share": hi_share}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-08-18")
    ap.add_argument("--end", default="2026-09-02")
    args = ap.parse_args()

    from quant.backtest.p4_ths_pool import load_cached, trade_dates
    dates = trade_dates(args.start, args.end)
    rows_by_date = {d: (load_cached(d) or []) for d in dates}
    lu = [len(rows_by_date[d]) for d in dates]
    conn_all = []
    mb_all = []
    for d in dates:
        rows = rows_by_date[d]
        boards = [x.get("board") or 1 for x in rows]
        mb_all.append(max(boards) if boards else 0)
        conn_all.append(sum(1 for b in boards if b >= 2))
    print(f"窗口 {args.start}~{args.end} {len(dates)}日 | lu p85={pct(lu,.85)} p90={pct(lu,.9)} "
          f"| 最高板 p90={pct(mb_all,.9)} | 连板家数 p90={pct(conn_all,.9)}")

    # ---------- 候选刻度 ----------
    cand_scales = [
        ("S0(现状70/6/25)", SentimentConfig(lu_scale=70, board_scale=6, ladder_scale=25)),
        ("S1(p90/p90/p90)", SentimentConfig(lu_scale=pct(lu, .9), board_scale=pct(mb_all, .9), ladder_scale=pct(conn_all, .9))),
        ("S2(p85/p85/p90)", SentimentConfig(lu_scale=pct(lu, .85), board_scale=pct(mb_all, .85), ladder_scale=pct(conn_all, .9))),
        ("S3(110/14/30)", SentimentConfig(lu_scale=110, board_scale=14, ladder_scale=30)),
    ]

    results = []
    for tag, sc in cand_scales:
        series = build_series_with(rows_by_date, dates, sc)
        heat = sorted(s.heat for s in series)
        q88, q70, q45, q18 = pct(heat, .88), pct(heat, .70), pct(heat, .45), pct(heat, .18)
        # 候选周期线：以自身 heat 分位为锚
        cand_cc = {
            "cc_q(88/70/45/18)": CycleConfig(heat_high=round(q88, 1), heat_warm=round(q70, 1),
                                             heat_cold=round(q18, 1), heat_launch=round(q45, 1),
                                             board_high=11, lu_high=90, lu_low=25,
                                             conn_high=20, zhaban_rate_high=0.35,
                                             premium_neg=-0.01, premium_pos=0.02),
            "cc_q-3(88-3...)": CycleConfig(heat_high=round(q88 - 3, 1), heat_warm=round(q70 - 3, 1),
                                           heat_cold=round(q18, 1), heat_launch=round(q45 - 3, 1),
                                           board_high=11, lu_high=90, lu_low=25,
                                           conn_high=20, zhaban_rate_high=0.35,
                                           premium_neg=-0.01, premium_pos=0.02),
            "cc_now(72/55/32/45)": CycleConfig(heat_high=72, heat_warm=55, heat_cold=32,
                                               heat_launch=45, board_high=11, lu_high=90,
                                               lu_low=25, conn_high=20, zhaban_rate_high=0.35,
                                               premium_neg=-0.01, premium_pos=0.02),
        }
        for ctag, cc in cand_cc.items():
            r = eval_config(dates, series, cc, tag=f"{tag}|{ctag}")
            results.append((tag, ctag, r))
    print("\n(参考现状：高潮命中98% 退潮命中59% 高潮占75% 退潮0天)")


if __name__ == "__main__":
    main()
