# -*- coding: utf-8 -*-
"""P4 校准器滚动化（2026-09-05）：复盘页「周期阶段分布 / 转折点命中率」从一次性标定
改为**随最新交易日滚动重算**——每日新样本纳入回放后重新自评。

口径一致性原则（与 p4_replay 2026-09-02 基线完全同源，零公式漂移）：
- 每日离线输入压缩为四元组 {d, lu, mb, conn}（同花顺涨停池派生：家数/最高板/连板家数）；
- 离线 heat/band 用 sentiment.heat_score/_band 原函数重建（缺炸板→该项跳过、
  缺隔日溢价→中值 7.5、无跌停→惩罚 0，故离线上限 ~82.5，与 P4 完全一致）；
- 周期阶段用 regime.cycle.classify(cur, prev) 原函数；
- 顶点/退潮兑现/谷底判定与命中统计直接复用 p4_replay.find_turning_points / evaluate；
- lu_min（顶点门槛 = 窗口涨停家数 p75）在**种子窗口一次性冻结**：阈值是标定物，
  不应随每日样本漂移；后续每日自评沿用同一门槛（存于 calib.series.lu_min）。

存储形态（NoSQL `calib` 集合；seed_calib 云函数导入种子，daily_job 每交易日增量）：
  doc series: {rows: [{d,lu,mb,conn}...], lu_min, updated_at}   # ~45B/日，年增约 11KB
  doc agg:    {window:{from,to,days}, stages:{启动/发酵/高潮/震荡/退潮: n},
               hits:{climax_total, strict, loose, retreat_total, retreat_hit, trough_total},
               last, updated_at}
幂等：evaluate_rows 为纯函数——同一序列重复计算结果逐位一致；daily_job 传入"不含当日"
的 rows，快照侧追加当日三元组后重算，同日多次触发安全。

用法：
  python3 -m quant.backtest.p4_eval                 # 自检：对照 P4 基线真值
  python3 -m quant.backtest.p4_eval --seed [end]    # 生成种子 JSON（rows + lu_min）
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from quant.backtest.p4_replay import evaluate, find_turning_points          # noqa: E402
from quant.backtest.p4_ths_pool import load_cached, trade_dates             # noqa: E402
from quant.indicators.sentiment import (                                    # noqa: E402
    DailySentiment, DEFAULT_SC, _band, heat_score)
from quant.regime.cycle import DEFAULT_CC, classify                         # noqa: E402

# P4 基线真值（2026-09-02 定案，254 日窗口）—— 自检断言用
BASELINE = {
    "window_days": 254,
    "stages": {"震荡": 123, "高潮": 78, "发酵": 34, "启动": 17, "退潮": 2},
    "hits": {"climax_total": 37, "strict": 25, "loose": 37,
             "retreat_total": 37, "retreat_hit": 32, "trough_total": 6},
}
SEED_START = "2025-08-18"


# ---------- 三元组 ----------

def row_of_ths(rows: list[dict], d: str) -> dict:
    """同花顺涨停池归一化行 → 当日离线四元组。"""
    boards = [int(x.get("board") or 1) for x in rows]
    return {
        "d": d,
        "lu": len(rows),
        "mb": max(boards) if boards else 0,
        "conn": sum(1 for b in boards if b >= 2),
    }


def rows_from_cache(start: str, end: str) -> list[dict]:
    """本地 P4 缓存 → 四元组序列（升序）。"""
    out = []
    for d in trade_dates(start, end):
        cached = load_cached(d)
        if cached:
            out.append(row_of_ths(cached, d))
    return out


# ---------- 重放（与 p4_replay 同源同口径） ----------

def synth(rows: list[dict]) -> list:
    """四元组 → DailySentiment 序列（heat/band 与离线回放逐位一致）。"""
    out = []
    for r in rows:
        s = DailySentiment(date=r["d"], lu_count=int(r["lu"]),
                           max_board=int(r["mb"]), conn_board_count=int(r["conn"]))
        s.heat = heat_score(s, DEFAULT_SC)
        s.band = _band(s.heat, DEFAULT_SC)
        out.append(s)
    return out


def lu_min_of(rows: list[dict]) -> int:
    """窗口涨停家数 p75（与 find_turning_points 缺省口径同式），种子期冻结。"""
    lu = sorted(int(r["lu"]) for r in rows)
    n = len(lu)
    return int(lu[min(n - 1, int(n * 0.75))])


def evaluate_rows(rows: list[dict], lu_min: int | None = None) -> dict:
    """纯函数：四元组序列 → 复盘页滚动校准结果。

    lu_min 缺省时按当前窗口 p75 自适应（仅建议种子期使用）；滚动路径应显式传
    冻结值，保证阈值不随样本漂移。
    """
    if not rows:
        raise ValueError("空序列")
    series = synth(rows)
    states = [classify(s, series[i - 1] if i >= 1 else None, DEFAULT_CC)
              for i, s in enumerate(series)]
    tp = find_turning_points(series, lu_min=lu_min)
    ev = evaluate(series, states, tp)
    stages: dict[str, int] = {}
    for c in states:
        stages[c.stage] = stages.get(c.stage, 0) + 1
    return {
        "window": {"from": rows[0]["d"], "to": rows[-1]["d"], "days": len(rows)},
        "stages": stages,
        "hits": {
            "climax_total": ev["climax_total"],
            "strict": ev["climax_hit_strict"],
            "loose": ev["climax_hit_loose"],
            "retreat_total": ev["retreat_total"],
            "retreat_hit": ev["retreat_hit"],
            "trough_total": ev["trough_total"],
        },
        "last_heat": series[-1].heat,
        "last_stage": states[-1].stage,
    }


# ---------- CLI ----------

def main():
    seed_mode = "--seed" in sys.argv
    end = "2026-09-02"
    if seed_mode:
        i = sys.argv.index("--seed")
        if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("-"):
            end = sys.argv[i + 1]
    if seed_mode:
        rows = rows_from_cache(SEED_START, end)
        lu_min = lu_min_of(rows)
        payload = {"rows": rows, "lu_min": lu_min, "generated_at_end": end}
        out = os.path.join(".workbuddy", "p4", "calib_seed.json")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        kb = os.path.getsize(out) / 1024
        print(f"种子已写 {out}: {len(rows)} 日 ({rows[0]['d']}~{rows[-1]['d']}), "
              f"lu_min={lu_min}, {kb:.1f}KB")
        return

    # 自检：254 日基线（冻结 lu_min 由该窗口计算）→ 对照 BASELINE
    rows254 = rows_from_cache(SEED_START, "2026-09-02")
    lm = lu_min_of(rows254)
    r254 = evaluate_rows(rows254, lu_min=lm)
    ok = True
    print(f"[254 日基线自检] lu_min(冻结)={lm}")
    if r254["window"]["days"] != BASELINE["window_days"]:
        ok = False
        print(f"  ✗ 窗口日数 {r254['window']['days']} != {BASELINE['window_days']}")
    for k, v in BASELINE["stages"].items():
        got = r254["stages"].get(k, 0)
        flag = "✓" if got == v else "✗"
        if got != v:
            ok = False
        print(f"  {flag} 阶段 {k}: {got} (基线 {v})")
    for k, v in BASELINE["hits"].items():
        got = r254["hits"][k]
        flag = "✓" if got == v else "✗"
        if got != v:
            ok = False
        print(f"  {flag} 命中 {k}: {got} (基线 {v})")
    print(f"  阶段合计 {sum(r254['stages'].values())} / 命中率 "
          f"严格 {r254['hits']['strict']}/{r254['hits']['climax_total']}、"
          f"宽松 {r254['hits']['loose']}/{r254['hits']['climax_total']}、"
          f"退潮 {r254['hits']['retreat_hit']}/{r254['hits']['retreat_total']}")
    print(f"  254 日自检: {'✅ 全部一致' if ok else '❌ 存在偏差，禁止上线'}")

    # 滚动演示：追加缓存内的新交易日（09-03/09-04）
    rows_all = rows_from_cache(SEED_START, "2026-09-04")
    extra = [r["d"] for r in rows_all[len(rows254):]]
    if extra:
        r_all = evaluate_rows(rows_all, lu_min=lm)  # lu_min 仍用种子冻结值
        print(f"\n[滚动演示] 追加 {extra} → {r_all['window']['days']} 日 "
              f"({r_all['window']['from']}~{r_all['window']['to']})")
        print(f"  阶段: {r_all['stages']}  合计 {sum(r_all['stages'].values())}")
        h = r_all["hits"]
        print(f"  命中: 顶点 {h['strict']}/{h['climax_total']}(严) "
              f"{h['loose']}/{h['climax_total']}(宽) | "
              f"退潮 {h['retreat_hit']}/{h['retreat_total']}")
        print(f"  最新: heat={r_all['last_heat']} stage={r_all['last_stage']}")


if __name__ == "__main__":
    main()
