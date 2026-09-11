# -*- coding: utf-8 -*-
"""异动偏离值引擎 CLI。

用法：
    python3 check_abnormal.py 000547 600519 300750
    python3 check_abnormal.py 000547 --bench sz399001 --json
    python3 check_abnormal.py --list  # 看内置校验案例

按《个人关于投机的理解与做法》+ 交易所规则：
偏离值 = 个股区间涨幅 - 基准指数区间涨幅。
普通异动：3日 |偏离| >= 20%(10cm)/30%(20cm)/15%(ST)
严重异动：10日 +100%/-50%、30日 +200%/-70%，或 10日内4次同向普通异动
"""
import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from quant.data.kline import (
    fetch_daily, normalize_code, benchmark_index, is_index,
)
from quant.indicators.abnormal import (
    compute_deviation, DEFAULT_CFG, DeviationResult,
)

PCT = lambda v: "—" if v is None else f"{v*100:+.1f}%"


def analyze(code: str, bench: str | None = None, count: int = 60, asof: str | None = None):
    code = normalize_code(code)
    if is_index(code):
        raise ValueError(f"{code} 是指数，请传个股代码")
    rows, name = fetch_daily(code, count=count)
    bench_code = bench or benchmark_index(code)
    bench_rows, bench_name = fetch_daily(bench_code, count=count)
    if asof:  # 回看历史某一日：只保留该日及以前的数据
        rows = [r for r in rows if r["date"] <= asof]
        bench_rows = [r for r in bench_rows if r["date"] <= asof]
        if not rows:
            raise ValueError(f"{code} 在 {asof} 前无数据")
    res = compute_deviation(
        rows, bench_rows, code, name=name or "",
        bench_code=bench_code, bench_name=bench_name or bench_code,
    )
    return res


def render(res: DeviationResult) -> str:
    flag = {"严重异动": "🚨", "普通异动": "⚠️", "高危接近": "🔶", "正常": "✅"}[res.risk_level]
    lines = [
        f"{flag} {res.name}({res.code})  [{res.board} 基准:{res.bench_name}]  截止{res.last_date}",
        f"    涨跌幅限制 {res.limit_pct*100:.0f}% | 近10日涨停 {res.limitup_10d} 次 / 近30日 {res.limitup_30d} 次",
        f"    偏离: 3日 {PCT(res.dev_3d)} (个股 {PCT(res.stock_3d)})"
        f" | 10日 {PCT(res.dev_10d)} (个股 {PCT(res.stock_10d)})"
        f" | 30日 {PCT(res.dev_30d)} (个股 {PCT(res.stock_30d)})",
    ]
    # 同向计数
    if res.same_dir_up_count or res.same_dir_down_count:
        lines.append(f"    10日同向普通异动: 上行 {res.same_dir_up_count} 次 / 下行 {res.same_dir_down_count} 次 (>=4 即严重异动)")
    # 严重异动余量（方向对称：涨|跌）
    if res.dev_10d is not None or res.dev_30d is not None:
        parts = []
        if res.dev_10d is not None:
            u = "已触" if res.serious_10d_up else f"+100%线差{res.headroom_10d_up*100:.1f}pp"
            d = "已触" if res.serious_10d_down else f"-50%线差{res.headroom_10d_down*100:.1f}pp"
            parts.append(f"10日[{u}|{d}]")
        if res.dev_30d is not None:
            u = "已触" if res.serious_30d_up else f"+200%线差{res.headroom_30d_up*100:.1f}pp"
            d = "已触" if res.serious_30d_down else f"-70%线差{res.headroom_30d_down*100:.1f}pp"
            parts.append(f"30日[{u}|{d}]")
        lines.append(f"    严重异动余量(涨|跌): {' '.join(parts)}")
    for n in res.notes:
        lines.append(f"    💡 {n}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="异动偏离值引擎 P1")
    ap.add_argument("codes", nargs="*", help="股票代码，如 000547 或 sz000547")
    ap.add_argument("--bench", help="覆盖基准指数代码")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--count", type=int, default=80, help="拉取K线条数")
    ap.add_argument("--asof", help="只看截止某日(YYYY-MM-DD)的历史状态，用于回测校验")
    args = ap.parse_args()

    if not args.codes:
        ap.print_help()
        sys.exit(1)

    results = []
    for raw in args.codes:
        try:
            r = analyze(raw, bench=args.bench, count=args.count, asof=args.asof)
            results.append(r)
        except Exception as e:
            print(f"✗ {raw}: {e}", file=sys.stderr)

    if args.json:
        payload = []
        for r in results:
            obj = dict(r.__dict__)
            obj["risk_level"] = r.risk_level
            payload.append(obj)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for i, r in enumerate(results):
            if i:
                print()
            print(render(r))


if __name__ == "__main__":
    main()
