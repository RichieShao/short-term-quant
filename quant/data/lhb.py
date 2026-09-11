# -*- coding: utf-8 -*-
"""龙虎榜（东方财富 datacenter-web，沙箱已验证可达）。

三张报表（均为**全市场按日**返回，故一天只需查 3~4 次，不做逐股请求）：
- ``RPT_DAILYBILLBOARD_DETAILSNEW``   当日上榜明细（含净买额/上榜原因/后续涨跌幅）
- ``RPT_ORGANIZATION_TRADE_DETAILS``  机构专用席位买卖
- ``RPT_BILLBOARD_DAILYDETAILSBUY``   买入营业部席位明细（游资识别）
- ``RPT_BILLBOARD_DAILYDETAILSSELL``  卖出营业部席位明细（若无则自动跳过）

⚠ 字段易混（2026-09-11 实测）：
    ``EXPLANATION`` = 上榜原因（"日跌幅偏离值达到7%的前5只证券"）
    ``EXPLAIN``     = 东财资金标签（"广东资金卖出，成功率33.44%"）
    ``BUY_SEAT`` / ``BUY_SEAT_NEW`` 是占位符 "11111"，**无意义**，席位名走
    ``RPT_BILLBOARD_DAILYDETAILS*`` 的 ``OPERATEDEPT_NAME``。

当日榜约 **18:00 之后**才发布，故 16:05/16:40 的盘后快照只能拿到 T-1 榜。

本模块会被 CloudBase Python3.7 云函数直接引用，故启用
``from __future__ import annotations``。
"""
from __future__ import annotations

import json

from quant.data.kline import _http, normalize_code

_BASE = "https://datacenter-web.eastmoney.com/api/data/v1/get"
_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://data.eastmoney.com/stock/tradedetail.html",
}

MAX_SEATS = 5          # 每侧最多保留的席位条数
_PAGE_SIZE = 500       # 单日明细最多 ~100 行，500 足够一页取全


def _dc(report: str, trade_date: str, page_size: int = _PAGE_SIZE,
        sort_columns: str = "", sort_types: str = "-1") -> list[dict]:
    """按交易日拉一张报表的全部行；失败返回 []（不抛，便于整链降级）。"""
    filt = "(TRADE_DATE%3D%27" + trade_date + "%27)"
    url = (_BASE + "?reportName=" + report
           + "&columns=ALL&filter=" + filt
           + "&pageSize=%d&pageNumber=1" % page_size
           + "&source=WEB&client=WEB")
    if sort_columns:
        url += "&sortColumns=" + sort_columns + "&sortTypes=" + sort_types
    try:
        raw = _http(url, timeout=15, headers=_UA)
        res = json.loads(raw).get("result") or {}
        return res.get("data") or []
    except Exception:
        return []


def _num(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _code_of(row: dict) -> str:
    """统一成带前缀小写代码；datacenter 的 SECUCODE 形如 '000017.SZ'。"""
    sec = str(row.get("SECUCODE") or "")
    if "." in sec:
        num, mk = sec.split(".", 1)
        mk = mk.upper()
        pre = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(mk)
        if pre:
            return pre + num
        return normalize_code(num)
    return normalize_code(str(row.get("SECURITY_CODE") or ""))


def _reasons(rows: list[dict]) -> list[str]:
    out = []
    for r in rows:
        t = (r.get("EXPLANATION") or "").strip()
        if t and t not in out:
            out.append(t)
    return out


def fetch_lhb_day(trade_date: str) -> dict:
    """拉取某交易日龙虎榜全量，返回按代码索引的字典。

    trade_date: ``YYYY-MM-DD``（东财 filter 用短横线格式）

    返回
    ----
    ``{date, n_codes, n_rows, ok, by_code: {code: {...}}, errors: [...]}``

    单只 code 结构::

        {code, name, date, net_amt, buy_amt, sell_amt, net_ratio,
         deal_ratio, accum_amount, turnover, pct, close, market,
         reasons: [...], explain,
         inst: {buy, sell, net, buy_times, sell_times} | None,
         seats_buy: [{name, buy, sell, net, rise3}] | [],
         seats_sell: [...], fwd: {d1, d2, d5, d10}}
    """
    errors: list[str] = []
    detail = _dc("RPT_DAILYBILLBOARD_DETAILSNEW", trade_date)
    if not detail:
        return {"date": trade_date, "n_codes": 0, "n_rows": 0, "ok": False,
                "by_code": {}, "errors": ["明细为空（榜未发布或日期非交易日）"]}

    # ---- 1) 明细：按代码归并（同股可能因多条上榜原因出现多行） ----
    grouped: dict[str, list[dict]] = {}
    for r in detail:
        c = _code_of(r)
        if not c:
            continue
        grouped.setdefault(c, []).append(r)

    by_code: dict[str, dict] = {}
    for c, rows in grouped.items():
        # 取净买额绝对值最大的一行为主行（同股多原因时代表主力方向）
        main = max(rows, key=lambda r: abs(_num(r.get("BILLBOARD_NET_AMT")) or 0))
        inst = None
        by_code[c] = {
            "code": c,
            "name": (main.get("SECURITY_NAME_ABBR") or "").strip(),
            "date": trade_date,
            "net_amt": _num(main.get("BILLBOARD_NET_AMT")),
            "buy_amt": _num(main.get("BILLBOARD_BUY_AMT")),
            "sell_amt": _num(main.get("BILLBOARD_SELL_AMT")),
            "net_ratio": _num(main.get("DEAL_NET_RATIO")),        # 净买额占总成交 %
            "deal_ratio": _num(main.get("DEAL_AMOUNT_RATIO")),    # 龙虎榜成交占总成交 %
            "accum_amount": _num(main.get("ACCUM_AMOUNT")),       # 当日总成交额
            "turnover": _num(main.get("TURNOVERRATE")),
            "pct": _num(main.get("CHANGE_RATE")),
            "close": _num(main.get("CLOSE_PRICE")),
            "market": (main.get("TRADE_MARKET") or "").strip(),
            "reasons": _reasons(rows),
            "explain": (main.get("EXPLAIN") or "").strip(),
            "n_reason": len(rows),
            "inst": inst,
            "seats_buy": [],
            "seats_sell": [],
            # 上榜后表现（T 日当天为 None，后续回补）
            "fwd": {
                "d1": _num(main.get("D1_CLOSE_ADJCHRATE")),
                "d2": _num(main.get("D2_CLOSE_ADJCHRATE")),
                "d5": _num(main.get("D5_CLOSE_ADJCHRATE")),
                "d10": _num(main.get("D10_CLOSE_ADJCHRATE")),
            },
        }

    # ---- 2) 机构专用席位 ----
    try:
        org = _dc("RPT_ORGANIZATION_TRADE_DETAILS", trade_date)
        for r in org:
            c = _code_of(r)
            node = by_code.get(c)
            if not node:
                continue
            buy = _num(r.get("BUY_AMT"))
            sell = _num(r.get("SELL_AMT"))
            net = _num(r.get("NET_BUY_AMT"))
            if net is None:
                net = (buy or 0) - (sell or 0)
            cur = node["inst"]
            node["inst"] = {
                "buy": buy,
                "sell": sell,
                "net": net,
                "ratio": _num(r.get("RATIO")),
                "buy_times": r.get("BUY_TIMES"),
                "sell_times": r.get("SELL_TIMES"),
                "buy_count": r.get("BUY_COUNT"),
                "sell_count": r.get("SELL_COUNT"),
            }
            if cur and cur.get("net") is not None:
                node["inst"]["net"] = (cur["net"] or 0) + (net or 0)
                node["inst"]["buy"] = (cur["buy"] or 0) + (buy or 0)
                node["inst"]["sell"] = (cur["sell"] or 0) + (sell or 0)
    except Exception as e:
        errors.append("机构席位: %s" % e)

    # ---- 3) 营业部席位（游资识别） ----
    def _seats(report: str, side: str):
        try:
            rows = _dc(report, trade_date, page_size=1000)
            for r in rows:
                c = _code_of(r)
                node = by_code.get(c)
                if not node:
                    continue
                node[side].append({
                    "name": (r.get("OPERATEDEPT_NAME") or "").strip(),
                    "buy": _num(r.get("BUY")),
                    "sell": _num(r.get("SELL")),
                    "net": _num(r.get("NET")),
                    "rise3": _num(r.get("RISE_PROBABILITY_3DAY")),  # 该席位3日上涨概率%
                })
        except Exception as e:
            errors.append("%s: %s" % (report, e))

    _seats("RPT_BILLBOARD_DAILYDETAILSBUY", "seats_buy")
    _seats("RPT_BILLBOARD_DAILYDETAILSSELL", "seats_sell")
    for node in by_code.values():
        node["seats_buy"] = sorted(
            node["seats_buy"], key=lambda s: -(s.get("buy") or 0))[:MAX_SEATS]
        node["seats_sell"] = sorted(
            node["seats_sell"], key=lambda s: -(s.get("sell") or 0))[:MAX_SEATS]

    return {
        "date": trade_date,
        "n_codes": len(by_code),
        "n_rows": len(detail),
        "ok": True,
        "by_code": by_code,
        "errors": errors[:6],
    }


def lhb_badges(node: dict | None) -> list[str]:
    """把一只票的龙虎榜信息压成短标签（前端徽章用）。"""
    if not node:
        return []
    tags = []
    net = node.get("net_amt")
    if net is not None:
        tags.append(("净买" if net > 0 else "净卖") + "%.2f亿" % (abs(net) / 1e8))
    inst = node.get("inst") or {}
    inet = inst.get("net")
    if inet is not None:
        tags.append(("机构净买" if inet > 0 else "机构净卖") + "%.2f亿" % (abs(inet) / 1e8))
    if node.get("n_reason", 0) > 1:
        tags.append("%d条上榜原因" % node["n_reason"])
    return tags


def fetch_lhb_pair(today: str, prev: str) -> dict:
    """同时取当日与前一交易日的榜（用户口径"两者都存"）。

    返回 ``{today: {...}, prev: {...}, prev_date: prev}``
    """
    return {
        "today": fetch_lhb_day(today) if today else None,
        "prev": fetch_lhb_day(prev) if prev else None,
        "prev_date": prev or None,
    }


if __name__ == "__main__":
    import sys
    d = sys.argv[1] if len(sys.argv) > 1 else "2026-09-11"
    snap = fetch_lhb_day(d)
    print("date=%s ok=%s codes=%d rows=%d errors=%s"
          % (snap["date"], snap["ok"], snap["n_codes"], snap["n_rows"], snap["errors"]))
    for c, v in list(snap["by_code"].items())[:3]:
        print(" ", c, v["name"], "净买=%.4f亿" % ((v["net_amt"] or 0) / 1e8),
              "| 机构=%s" % (v["inst"] is not None),
              "| 买席位=%d 卖席位=%d" % (len(v["seats_buy"]), len(v["seats_sell"])),
              "| 原因=%s" % (v["reasons"][:1]))
