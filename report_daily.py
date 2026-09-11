# -*- coding: utf-8 -*-
"""每日盘后报告 CLI（P2）。

用法：
    python3 report_daily.py            # 今日盘后报告
    python3 report_daily.py --date 2026-09-01   # 历史某日(回看)
    python3 report_daily.py --out reports/2026-09-02_盘后.md
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from quant.report.daily import build_report


def main():
    ap = argparse.ArgumentParser(description="每日盘后报告 P2")
    ap.add_argument("--date", help="报告日期 YYYY-MM-DD，默认最新交易日")
    ap.add_argument("--out", help="输出 .md 路径（默认 reports/ 下自动命名 + 打印摘要）")
    args = ap.parse_args()

    t0 = time.time()
    md = build_report(args.date)
    print(f"[耗时 {time.time()-t0:.1f}s]")

    if args.out:
        path = args.out
    else:
        date_tag = args.date or md.split()[3].strip("#") if False else None
        # 从报告标题行取日期
        import re
        m = re.search(r"# 短线情绪盘后报告 (\S+)", md)
        tag = m.group(1) if m else time.strftime("%Y-%m-%d")
        os.makedirs("reports", exist_ok=True)
        path = f"reports/{tag}_盘后.md"

    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"已保存: {os.path.abspath(path)}")
    # 控制台只打前 40 行摘要
    print("\n".join(md.split("\n")[:40]))


if __name__ == "__main__":
    main()
