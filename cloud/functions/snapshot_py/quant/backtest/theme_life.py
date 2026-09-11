# -*- coding: utf-8 -*-
"""题材生命期聚合（增量可维护版，供每日自动更新）

背景：复盘页「题材生命期 TOP15」原为 P4 一次性产物（themes_top.md），
本模块把同口径统计改为**可每日增量**的结构：

  agg = {"last": "YYYY-MM-DD",
         "themes": {tag: {"days": int(出现交易日数), "peak": int(峰值单日家数),
                          "first": 首现日期, "last": 最近出现日期}}}

增量语义：
  - 同一天重复调用必须幂等：调用方保证 agg["last"] < date 才更新；
  - 每日该 tag 出现一次 days+1，peak=max(peak, 当日家数)，first/last 延展。

标签口径与 P4 完全一致：同花顺涨停 reason 按 "+" 拆分 + 停用词剔除
（_TAG_STOP/_tags_of 为唯一来源，p4_replay.py 已改为引用本模块）。

云端 Python3.7 兼容。仅依赖 quant.data.kline(p4_ths_pool)。
"""
from __future__ import annotations

import datetime as _dt

# 题材统计剔除的泛用词（非题材属性）—— 与 P4 校准同源（曾定义于 p4_replay.py）
_TAG_STOP = {
    "三季报增长", "年报增长", "季报增长", "半年报增长", "一季报增长", "业绩增长", "业绩预增",
    "回购", "高送转", "次新股", "超跌反弹", "低价股", "ST摘帽", "举牌", "股权转让",
    "股东增持", "并购重组", "定增", "国企改革", "央企改革", "破净股", "昨日涨停",
    "融资融券", "深股通", "沪股通", "机构重仓", "基金重仓", "预亏", "预盈", "摘帽",
    "华为概念",  # 仅示例，真实停用词按需增补
}


def _tags_of(reason: str):
    """reason_type（'+' 分隔的多标签）→ 剔除泛用词后的题材标签迭代器。"""
    for t in str(reason).split("+"):
        t = t.strip()
        if t and t not in _TAG_STOP:
            yield t


def counts_of_rows(rows: list[dict]) -> dict[str, int]:
    """当日涨停池（p4_ths_pool normalized 行，含 reason）→ {题材: 当日家数}。"""
    out: dict[str, int] = {}
    for r in rows:
        for t in _tags_of(r.get("reason", "")):
            out[t] = out.get(t, 0) + 1
    return out


def new_agg() -> dict:
    return {"last": "", "themes": {}}


def agg_update(agg: dict, date: str, counts: dict) -> dict:
    """增量并入一天（date 升序；调用方负责幂等防重）。返回同一 agg。"""
    themes = agg.setdefault("themes", {})
    for tag, c in (counts or {}).items():
        a = themes.setdefault(tag, {"days": 0, "peak": 0, "first": date, "last": date})
        a["days"] = a.get("days", 0) + 1
        a["peak"] = max(a.get("peak", 0), c)
        if not a.get("first") or date < a["first"]:
            a["first"] = date
        if not a.get("last") or date > a["last"]:
            a["last"] = date
    if date > agg.get("last", ""):
        agg["last"] = date
    return agg


def agg_from_cache(start: str, end: str) -> dict:
    """种子：遍历本地 P4 缓存（.workbuddy/p4/zt/*.json）逐日累计 → agg。"""
    from quant.backtest.p4_ths_pool import load_cached, trade_dates
    agg = new_agg()
    for d in trade_dates(start, end):
        rows = load_cached(d.replace("-", ""))
        if rows:
            agg_update(agg, d, counts_of_rows(rows))
    return agg


def to_top(agg: dict, n: int = 15) -> list[dict]:
    """按峰值单日家数降序取 TOP n。"""
    items = []
    for tag, a in (agg.get("themes") or {}).items():
        items.append({"name": tag, "peak": a.get("peak", 0),
                      "days": a.get("days", 0),
                      "first": a.get("first", ""), "last": a.get("last", "")})
    items.sort(key=lambda x: (x["peak"], x["days"]), reverse=True)
    return items[:n]


if __name__ == "__main__":
    import json
    agg = agg_from_cache("2025-08-18", "2026-09-04")
    print(f"窗口至 {agg['last']}：题材 {len(agg['themes'])} 个")
    print(json.dumps(to_top(agg, 15), ensure_ascii=False, indent=1))
