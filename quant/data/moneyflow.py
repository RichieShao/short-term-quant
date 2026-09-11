# -*- coding: utf-8 -*-
"""个股资金流：当日明细（东财）+ 多日趋势（自累积 → 东财 → 新浪三级来源）。

为什么是多级来源
----------------
东财 ``push2his/api/qt/stock/fflow/daykline/get``（唯一官方多日接口）**已失效**：
2026-09-11 实测，沙箱（curl 52 / urllib RemoteDisconnected）与云端云函数（一并发
RemoteDisconnected，自动回落到 push2delay）**双双失败**；``fflow/kline`` 旧路径、
``+cb``、``+_ts``、``61.push2his``、http、无 ut 等 9 种变体同样全挂。因此：

1. **当日明细** → 东财 ``push2delay``（实测沙箱 + 云端均可，只回最新 1 日）
2. **多日趋势**（近 3/5 日累计主力净额、连续净流入天数）三级来源：
   a. ``agg`` 自累积表（``flow_hist`` 集合，**东财口径，首选**；需连续运行数个交易日）
   b. 东财多日接口（若日后恢复，自动启用）
   c. 新浪 ``MoneyFlow.ssl_qsfx_zjlrqs``（20 日立即可用，但**口径不同源**，
      强制标 ``trend_src="sina"``）

⚠ 口径差异（务必在 UI 标注）：东财 主力净额 = 大单 + 超大单；新浪 ``netamount`` 是
"净流入额"，绝对值不可比（同票实测约差 1.9 倍），仅方向/趋势可参考。故多日字段一律
带 ``trend_src``（``agg`` / ``em`` / ``sina``）与 ``trend_base``。

fields2 为 15 列 CSV，按序：
    0  date              1  主力净额        2  小单净额      3  中单净额
    4  大单净额          5  超大单净额      6  主力净占比    7  小单净占比
    8  中单净占比        9  大单净占比     10  超大单净占比 11  收盘价
   12  涨跌幅%          13/14 恒为 0.00
恒等关系（东财口径）：主力净额 = 大单净额 + 超大单净额。

secid 市场前缀（2026-09-11 实测）
    sh（60/68/9…）→ ``1.``    sz / bj（000/002/300/301/920…）→ ``0.``
    ⚠ 北交所旧段 ``8xxxxx`` / ``4xxxxx`` 在本族接口不可用（rc=100，代码已迁 920 段）。

本模块会被 CloudBase Python3.7 云函数直接引用，故启用
``from __future__ import annotations`` 以兼容 PEP604 写法（X | None）。
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from quant.data.kline import _http, normalize_code

EM_UT = "b2884a393a59ad64002292a3e90d46a5"
_F1 = "f1,f2,f3,f7"
_F2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"

_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://data.eastmoney.com/zjlx/",
}

# 顺序即优先级；实测两端点在沙箱/云端的可用性不同，故轮询后取"行数最多"的结果
_HOSTS = (
    "https://push2his.eastmoney.com",
    "https://push2delay.eastmoney.com",
)

SINA_URL = ("https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            "MoneyFlow.ssl_qsfx_zjlrqs")
_SINA_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
}

DEFAULT_DAYS = 10


def secid(code: str) -> str:
    """``sh600237`` → ``1.600237``；``sz300563`` / ``bj920819`` → ``0.300563`` / ``0.920819``。"""
    c = normalize_code(str(code or ""))
    if c.startswith("sh"):
        return "1." + c[2:]
    if c.startswith(("sz", "bj")):
        return "0." + c[2:]
    return ("1." if c.startswith(("6", "9")) else "0.") + c


# ---------------------------------------------------------------- 东财 当日/多日

def _parse_klines(klines: list) -> list:
    """CSV → 结构化（保持接口原序，升序，最新在最后）。"""
    out = []
    for line in klines or []:
        p = str(line).split(",")
        if len(p) < 13:
            continue
        try:
            out.append({
                "date": p[0],
                "main_net": float(p[1]),      # 主力净额（元）
                "s_net": float(p[2]),         # 小单净额
                "m_net": float(p[3]),         # 中单净额
                "l_net": float(p[4]),         # 大单净额
                "xl_net": float(p[5]),        # 超大单净额
                "main_ratio": float(p[6]),    # 主力净占比 %
                "s_ratio": float(p[7]),
                "m_ratio": float(p[8]),
                "l_ratio": float(p[9]),
                "xl_ratio": float(p[10]),
                "close": float(p[11]),
                "pct": float(p[12]),
            })
        except (ValueError, IndexError):
            continue
    out.sort(key=lambda r: r["date"])
    return out


def _fetch_raw(code: str, days: int):
    """轮询所有主机，返回 (klines, 命中的主机)。全部失败返回 ([], "")."""
    sd = secid(code)
    best, best_host, last_err = [], "", ""
    for host in _HOSTS:
        url = (host + "/api/qt/stock/fflow/daykline/get"
               + "?lmt=%d&klt=101&secid=%s" % (days, sd)
               + "&fields1=" + _F1 + "&fields2=" + _F2 + "&ut=" + EM_UT)
        for _ in range(2):
            try:
                raw = _http(url, timeout=12, headers=_UA)
                data = (json.loads(raw).get("data") or {})
                rows = _parse_klines(data.get("klines") or [])
            except Exception as e:  # 网络/解析失败都降级
                last_err = "%s: %s" % (type(e).__name__, e)
                rows = []
            if len(rows) > len(best):
                best, best_host = rows, host
            if len(rows) >= days:
                return best, best_host
            if rows:
                break  # 该主机有响应就不重试
    if not best and last_err:
        raise RuntimeError(last_err)
    return best, best_host


# ---------------------------------------------------------------- 新浪 多日兜底

def query_sina_rows(code: str, num: int = 20) -> list:
    """新浪资金流历史（近 num 个交易日，升序）。

    字段：``net`` 净流入额（元）/ ``r0`` 超大单净流入（元）/ ``ratio`` 净流入率。
    ⚠ 与东财不同源，仅供趋势参考。
    """
    c = normalize_code(str(code or ""))
    url = "%s?page=1&num=%d&sort=opendate&asc=0&daima=%s" % (SINA_URL, num, c)
    raw = _http(url, timeout=12, headers=_SINA_UA)
    i = raw.find("[")
    if i < 0:
        return []
    out = []
    for r in json.loads(raw[i:]) or []:
        try:
            out.append({
                "d": str(r.get("opendate") or "")[:10],
                "net": float(r.get("netamount") or 0),
                "r0": float(r.get("r0_net") or 0),
                "ratio": float(r.get("ratioamount") or 0),
            })
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda x: x["d"])
    return out


# ---------------------------------------------------------------- 趋势计算

def _sign_streak(vals: list) -> int:
    """从最后一个值向前数"同号连续天数"；净流入为正、净流出为负。"""
    if not vals:
        return 0
    last = vals[-1]
    sign = 1 if last > 0 else (-1 if last < 0 else 0)
    if not sign:
        return 0
    n = 0
    for v in reversed(vals):
        if v * sign > 0:
            n += 1
        else:
            break
    return n * sign


def _trend(vals: list, n: int = 5):
    """返回 (sum3, sum5, 连续净流入天数, 样本天数)。不足窗口的累计值给 None。"""
    m = len(vals)
    return (sum(vals[-3:]) if m >= 3 else None,
            sum(vals[-5:]) if m >= 5 else None,
            _sign_streak(vals), m)


def _agg_series(agg, code: str, before_date: str) -> list:
    """从自累积表取"严格早于 before_date"的主力净额序列（升序）。

    agg 形如 ``{code: [{"d": "2026-09-10", "m": -1.2e8}, ...]}``（daily_job 从
    ``flow_hist`` 集合读出后注入）。
    """
    vals = []
    for r in (agg or {}).get(code) or []:
        try:
            d = str(r.get("d") or "")
            if d and d < before_date:
                vals.append((d, float(r.get("m"))))
        except (TypeError, ValueError):
            continue
    vals.sort(key=lambda x: x[0])
    return [v for _, v in vals]


def flow_tag(main_net, main_ratio) -> str:
    """资金标签（阈值口径，供前端配色/排序）。"""
    if main_net is None:
        return "无数据"
    r = main_ratio if main_ratio is not None else 0.0
    if main_net > 0:
        return "强流入" if r >= 10 else "流入"
    if main_net < 0:
        return "强流出" if r <= -10 else "流出"
    return "中性"


# ---------------------------------------------------------------- 对外接口

def query_flow(code: str, days: int = DEFAULT_DAYS, agg=None) -> dict | None:
    """单只资金流。返回 None 表示无数据（北交所旧段、停牌、接口全挂等）。"""
    c = normalize_code(str(code or ""))
    rows, host = _fetch_raw(c, days)
    if not rows:
        return None
    last = rows[-1]
    main, ratio = last["main_net"], last["main_ratio"]
    rec = {
        "code": c,
        "date": last["date"],
        "main_net": main,                     # 当日主力净额（元，东财口径）
        "main_ratio": ratio,                  # 当日主力净占比 %
        "xl_net": last["xl_net"],             # 超大单净额
        "xl_ratio": last["xl_ratio"],
        "l_net": last["l_net"],               # 大单净额
        "l_ratio": last["l_ratio"],
        "m_net": last["m_net"],               # 中单净额
        "s_net": last["s_net"],               # 小单净额
        "close": last["close"],
        "pct": last["pct"],
        "tag": flow_tag(main, ratio),
        "days": len(rows),
        "host": host,
        # 多日趋势（来源见 trend_src）
        "sum3": None, "sum5": None, "streak": None,
        "trend_src": None, "trend_base": None, "trend_days": 0,
    }
    # ① 自累积（东财口径，首选）：历史序列 + 今日，才是真正的"近 N 日累计"
    hist = _agg_series(agg, c, last["date"])
    if hist:
        s3, s5, st, n = _trend(hist + [main])
        rec.update(sum3=s3, sum5=s5, streak=st, trend_days=n,
                   trend_src="agg", trend_base="em_main_net")
    # ② 东财多日接口（若日后恢复，rows 会 >1 天）
    if rec["sum3"] is None and len(rows) >= 3:
        s3, s5, st, n = _trend([r["main_net"] for r in rows])
        rec.update(sum3=s3, sum5=s5, streak=st, trend_days=n,
                   trend_src="em", trend_base="em_main_net")
    # ③ 新浪兜底（口径不同源，必须带标记）
    if rec["sum3"] is None:
        try:
            sr = query_sina_rows(c, num=max(days, 20))
        except Exception:
            sr = []
        if sr and str(sr[-1]["d"]) == rec["date"]:
            s3, s5, st, n = _trend([x["net"] for x in sr])
            rec.update(sum3=s3, sum5=s5, streak=st, trend_days=n,
                       trend_src="sina", trend_base="sina_netamount",
                       sina_r0_net=sr[-1]["r0"], sina_ratio=sr[-1]["ratio"])
    return rec


def query_flows(codes: list, days: int = DEFAULT_DAYS, agg=None,
                max_workers: int = 8) -> dict:
    """并发批量取资金流。

    返回 ``{flows: {code: {...}}, errors: [...], hit_n, ask_n, days, srcs: {...}}``
    ``agg`` 为自累积表（见 ``_agg_series``），由 daily_job 从 ``flow_hist`` 读出注入。
    """
    uniq, seen = [], set()
    for c in codes or []:
        k = normalize_code(str(c or ""))
        if k and k not in seen:
            seen.add(k)
            uniq.append(k)

    flows, errors = {}, []
    if not uniq:
        return {"flows": {}, "errors": [], "hit_n": 0, "ask_n": 0,
                "days": days, "srcs": {}}

    def work(c):
        try:
            return c, query_flow(c, days=days, agg=agg), None
        except Exception as e:
            return c, None, "%s: %s" % (type(e).__name__, e)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for c, r, err in ex.map(work, uniq):
            if err:
                errors.append("%s %s" % (c, err))
            elif r:
                flows[c] = r

    srcs = {}
    for v in flows.values():
        k = v.get("trend_src") or "none"
        srcs[k] = srcs.get(k, 0) + 1
    return {"flows": flows, "errors": errors[:8], "hit_n": len(flows),
            "ask_n": len(uniq), "days": days, "srcs": srcs}


if __name__ == "__main__":
    import sys
    cs = sys.argv[1:] or ["sh600237", "sz300563", "sz000001", "bj920819"]
    res = query_flows(cs, days=10)
    print("asks=%d hits=%d srcs=%s errors=%s"
          % (res["ask_n"], res["hit_n"], res["srcs"], res["errors"]))
    for k, v in res["flows"].items():
        print("  %s %s 主力=%.2f亿 净占比=%.2f%% sum3=%s sum5=%s 连续=%s(%s)"
              % (k, v["tag"], (v["main_net"] or 0) / 1e8, v["main_ratio"] or 0,
                 ("%.2f亿" % (v["sum3"] / 1e8)) if v["sum3"] is not None else "-",
                 ("%.2f亿" % (v["sum5"] / 1e8)) if v["sum5"] is not None else "-",
                 v["streak"], v["trend_src"]))
