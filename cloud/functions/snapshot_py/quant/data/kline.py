# -*- coding: utf-8 -*-
"""日K行情抓取：腾讯主源 + 新浪回退。

接口：
- 腾讯: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{count},{fq}
- 新浪: https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol={code}&scale=240&datalen={count}

均返回 [{date, open, close, high, low, volume}, ...]（升序，最新在最后）。

注：本模块需被 CloudBase Python3.7 云函数直接引用，故启用
`from __future__ import annotations` 以兼容 PEP604 写法（X | None）。
"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://gu.qq.com/",
}

# 本机沙箱证书链不全，先正常校验，失败则回退不校验
def _make_ctx():
    ctx = ssl.create_default_context()
    return ctx

_CTX = _make_ctx()
_CTX_INSECURE = ssl._create_unverified_context()


def _http(url: str, timeout: float = 8.0, headers: dict | None = None) -> str:
    req = urllib.request.Request(url, headers=headers or UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
            return resp.read().decode("utf-8", "replace")
    except (ssl.SSLError, urllib.error.URLError, OSError):
        # 沙箱证书链不全，回退不校验证书（仅本地分析用）
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX_INSECURE) as resp:
            return resp.read().decode("utf-8", "replace")


def fetch_tencent(code: str, count: int = 160, fq: str = "qfq"):
    """code 形如 sh600519 / sz300750；返回 (rows, name)。fq: qfq前复权 | bfq不复权 | hfq后复权"""
    param_fq = "" if fq == "bfq" else "," + fq
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{count}{param_fq}"
    data = json.loads(_http(url))
    node = data.get("data", {}).get(code)
    if not node:
        raise ValueError(f"腾讯无数据: {code}")
    key = fq + "day" if fq != "bfq" else "day"
    rows_raw = node.get(key) or node.get("day") or []
    rows = []
    for r in rows_raw:
        try:
            rows.append({
                "date": r[0],
                "open": float(r[1]),
                "close": float(r[2]),
                "high": float(r[3]),
                "low": float(r[4]),
                "volume": float(r[5]),
            })
        except (ValueError, IndexError):
            continue
    name = None
    qt = node.get("qt", {}).get(code)
    if qt and len(qt) > 1:
        name = qt[1]
    return rows, name


def fetch_sina(code: str, count: int = 160):
    """code 形如 sh600519。新浪无名称，需外部补充。scale=240 即日线。"""
    url = f"https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol={code}&scale=240&ma=no&datalen={count}"
    text = _http(url)
    # 新浪可能返回 jsonp 或 js 前缀
    text = text.strip()
    start = text.find("[")
    if start < 0:
        raise ValueError(f"新浪无数据: {code}")
    arr = json.loads(text[start:])
    rows = []
    for r in arr:
        rows.append({
            "date": r["day"][:10],
            "open": float(r["open"]),
            "close": float(r["close"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "volume": float(r.get("volume", 0) or 0),
        })
    return rows


def fetch_daily(code: str, count: int = 160, fq: str = "qfq"):
    """统一入口：先腾讯后新浪。返回 (rows, name)。"""
    try:
        return fetch_tencent(code, count=count, fq=fq)
    except Exception as e:
        try:
            rows = fetch_sina(code, count=count)
            return rows, None
        except Exception as e2:
            raise RuntimeError(f"行情获取失败 {code}: tencent={e}; sina={e2}") from e2


def fetch_realtime(codes: list[str], timeout: float = 8.0) -> dict[str, dict]:
    """腾讯批量实时行情。codes 带前缀(sh/sz/bj)。返回 {code: {name, price, prev_close, pct}}。

    qt.gtimg.cn 文本格式字段：0=市场 1=名称 2=代码 3=现价 4=昨收 5=今开 ...
    """
    out = {}
    for i in range(0, len(codes), 60):
        part = codes[i:i + 60]
        url = "https://qt.gtimg.cn/q=" + ",".join(part)
        text = _http(url, timeout=timeout)
        for line in text.strip().split(";"):
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, payload = line.split("=", 1)
            key = key.replace("v_", "").strip()
            if not payload.startswith('"'):
                continue
            f = payload.strip('"').split("~")
            if len(f) < 5:
                continue
            try:
                price = float(f[3])
                prev = float(f[4])
                pct = (price - prev) / prev if prev else 0.0
            except ValueError:
                continue
            out[key] = {"name": f[1], "price": price, "prev_close": prev, "pct": pct}
    return out


def prev_trade_date(rows: list[dict], asof: str | None = None) -> str | None:
    """给定升序日K，返回 asof(默认最后一日)的前一交易日日期。"""
    dates = [r["date"] for r in rows]
    if not dates:
        return None
    if asof is None:
        return dates[-2] if len(dates) >= 2 else None
    prior = [d for d in dates if d < asof]
    return prior[-1] if prior else None


# ---------- 代码规范化与板块识别 ----------

def normalize_code(raw: str) -> str:
    """'600519'->'sh600519'；'sz300750'/'300750'->'sz300750'；已带前缀则原样返回（小写）。"""
    raw = raw.strip().lower()
    if raw[:2] in ("sh", "sz", "bj"):
        return raw
    if raw.startswith(("60", "68", "9")):
        return "sh" + raw
    if raw.startswith(("00", "30", "20", "15", "16")):
        return "sz" + raw
    if raw.startswith(("43", "83", "87", "88", "92")):
        return "bj" + raw
    return "sh" + raw  # 兜底


# 常见指数白名单（normalize 后全小写带前缀）。注意：sz000547 等 000 开头是深市个股，不算指数。
INDEX_WHITELIST = {
    "sh000001",  # 上证指数
    "sh000016",  # 上证50
    "sh000300",  # 沪深300
    "sh000905",  # 中证500
    "sh000852",  # 中证1000
    "sh000688",  # 科创50
    "sh000680",  # 科创综指（科创板全样本，2025-01-20发布，基准用）
    "sz399001",  # 深证成指
    "sz399005",  # 中小板指
    "sz399006",  # 创业板指
    "sz399102",  # 创业板综
    "sz399106",  # 深证综指
    "bj899050",  # 北证50
}


def is_index(code: str) -> bool:
    """仅白名单视为指数；sz000547 这类深市个股不是指数。"""
    return normalize_code(code) in INDEX_WHITELIST


def board_limit(code: str, name: str | None = None) -> float:
    """返回涨跌停幅度(小数)。ST=5cm；主板=10cm；创业板/科创=20cm；北交所=30cm。"""
    is_st = bool(name) and ("st" in name.lower())
    if is_st:
        return 0.05
    c = code[2:] if code[:2] in ("sh", "sz", "bj") else code
    if c.startswith(("300", "301", "302")) or c.startswith(("688", "689")):
        return 0.20
    if code[:2] == "bj":
        return 0.30
    return 0.10


def benchmark_index(code: str) -> str:
    """板块基准指数（默认映射，可被 CLI --bench 覆盖）。

    全样本可比口径（2026-09-02 定）：20cm 板块用"综合指数"而非"成份指数"，
    因成份指数受权重股扰动，会系统性扭曲个股偏离值：
      - 创业板：**创业板综 sz399102**（原 sz399006 创业板指为100权重样本，当前窗口差 ~8.1pp）
      - 科创板：**科创综指 sh000680**（2025-01-20发布，全样本；原 sh000688 科创50 仅50只，
        当前30日窗口差 ~7.7pp，权重股寒武纪/海光/中芯领跌时科创50系统性高估偏离）
    两口径差随对齐窗口漂移（停牌股窗口错位时非严格常数），绕异动判定以引擎默认口径为准。
    """
    c = code[2:] if code[:2] in ("sh", "sz", "bj") else code
    if code[:2] == "bj":
        return "bj899050"  # 北证50
    if c.startswith(("300", "301", "302")):
        return "sz399102"  # 创业板综（全样本口径）
    if c.startswith(("688", "689")):
        return "sh000680"  # 科创综指（全样本口径）
    if code.startswith("sh"):
        return "sh000001"  # 上证指数
    return "sz399001"  # 深证成指
