# -*- coding: utf-8 -*-
"""涨停/跌停/炸板池抓取（东方财富 push2ex，沙箱已验证可达）。

接口：
- 涨停池 getTopicZTPool  date=YYYYMMDD
- 跌停池 getTopicDTPool
- 炸板池 getTopicZBPool

返回归一化 list[dict]，字段：code(带前缀) / name / pct / board_cnt(连板数)
/ first_seal(首封HHMMSS, 有则int) / zhaban_cnt(炸板次数) / industry / zttj("N天M板")
"""

from __future__ import annotations
import json

from quant.data.kline import _http

EM_UT = "7eea3edcaed734bea9cbfc24409ed989"
_BASE = "https://push2ex.eastmoney.com"


def _pool(kind: str, date: str, max_items: int = 800) -> list[dict]:
    """kind: ZT / DT / ZB；date: 'YYYYMMDD'。翻页取全。"""
    url = f"{_BASE}/getTopic{kind}Pool?ut={EM_UT}&dpt=wz.ztzt"
    items, page = [], 0
    while len(items) < max_items and page < 6:
        u = (url
             + f"&Pageindex={page}&pagesize=200&sort=fbt%3Aasc"
             + (f"&date={date}" if date else ""))
        if kind == "DT":
            u = u.replace("sort=fbt%3Aasc", "sort=fund%3Aasc")
        elif kind == "ZB":
            u = u.replace("sort=fbt%3Aasc", "sort=zbc%3Adesc")
        raw = _http(u)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            break
        pool = ((data.get("data") or {}).get("pool")) or []
        if not pool:
            break
        items.extend(pool)
        tc = (data.get("data") or {}).get("tc") or 0
        if len(items) >= tc:
            break
        page += 1
    return _normalize(items, kind)


def _normalize(rows: list[dict], kind: str) -> list[dict]:
    out = []
    for r in rows:
        code = _market_prefix(r.get("c", ""), r.get("m", 0))
        zttj = r.get("zttj") or {}
        if isinstance(zttj, dict):
            zttj_txt = f"{zttj.get('days',1)}天{zttj.get('ct',1)}板"
        else:
            zttj_txt = ""
        out.append({
            "code": code,
            "name": r.get("n", ""),
            "pct": r.get("zdp", 0) / 100.0 if r.get("zdp") is not None else None,
            "board_cnt": r.get("lbc", 1) if kind == "ZT" else (1 if kind == "DT" else 0),
            "first_seal": int(r["fbt"]) if r.get("fbt") and kind == "ZT" else None,
            "zhaban_cnt": r.get("zbc", 0),
            "industry": r.get("hybk", ""),
            "zttj": zttj_txt,
            # 容量维度（2026-09-05 新增）：仓位管理的依据——成交额(元)/流通市值(元)/换手率(%)
            # 东财原始字段 amount=成交额 ltsz=流通市值 hs=换手率；DT/ZB 池同样携带
            "amount": r.get("amount"),
            "float_cap": r.get("ltsz"),
            "turnover": (r.get("hs") / 100.0 if isinstance(r.get("hs"), (int, float)) else None),
        })
    return out


def _market_prefix(code: str, market: int) -> str:
    """东财市场: 0=深(含北交所? 8/4开头), 1=沪。保守映射: 1→sh，其余按首位判断。"""
    if market == 1:
        return "sh" + code
    if code.startswith(("4", "8", "92")):
        return "bj" + code
    return "sz" + code


def fetch_zt_pool(date: str = "") -> list[dict]:
    return _pool("ZT", date)


def fetch_dt_pool(date: str = "") -> list[dict]:
    return _pool("DT", date)


def fetch_zb_pool(date: str = "") -> list[dict]:
    return _pool("ZB", date)


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else ""
    zt = fetch_zt_pool(date)
    dt = fetch_dt_pool(date)
    zb = fetch_zb_pool(date)
    print(f"date={date or 'today'} 涨停 {len(zt)} | 跌停 {len(dt)} | 炸板 {len(zb)}")
    for x in zt[:5]:
        print(" ", x)
