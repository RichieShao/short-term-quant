# -*- coding: utf-8 -*-
"""P4 回测数据管线一：同花顺涨停池全窗口抓取 + 本地缓存。

背景（2026-09-02 实测数据边界）：
- 东财 ZT/DT/ZB 三池：仅保留 ~21 自然日（15 交易日，2026-08-13 起）→ 历史不可用
- 同花顺 limit_up_pool：保留 ~1 年（2025-08 下旬 起），含 连板数/首封时间/涨停题材
- 结论：2023/2024 原定题材样本数据不可达；本模块用 THS 重建"窗口内全部交易日"的
  涨停池序列，供 p4_replay 做 温度/周期 回放校准。

接口字段（同花顺 limit_up_pool，field 映射）：
  code/name/high_days("N天M板")/high_days_value(&0xFFFF=板数)/first_limit_up_time(秒)
  last_limit_up_time(秒)/reason_type(涨停题材)/limit_up_type(换手/一字等)/change_rate
  market_type(HS/GEM/STAR?) / market_id

用法：
  python3 -m quant.backtest.p4_ths_pool 2025-08-20 2026-09-02
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from quant.data.kline import _http, fetch_daily  # noqa: E402

# 同花顺 dataapi 常量
THS_UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://data.10jqka.com.cn/"}
_FIELDS = "199112,10,9001,330323,330324,330325,330329,133338,133333,133303"
_POOL_URL = ("https://data.10jqka.com.cn/dataapi/limit_up/limit_up_pool"
             f"?page={{page}}&limit=100&field={_FIELDS}"
             "&filter=HS,GEM2STAR&order_field=330324&order_type=0&date={date}")

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                     ".workbuddy", "p4", "zt")
CACHE = os.path.abspath(CACHE)

_TZ8 = dt.timezone(dt.timedelta(hours=8))


def _to_hms(ts: int | None) -> str | None:
    """unix 秒 → HHMMSS（北京时间）。"""
    if not ts:
        return None
    t = dt.datetime.fromtimestamp(int(ts), tz=_TZ8)
    return f"{t:%H%M%S}"


def _board_of(high_days_value, high_days_txt) -> int:
    """连板数：high_days_value 低16位；异常回退解析 'N天M板'。"""
    if high_days_value:
        b = int(high_days_value) & 0xFFFF
        if b > 0:
            return b
    if high_days_txt:
        try:
            return int(high_days_txt.split("天")[-1].replace("板", ""))
        except Exception:
            pass
    return 1


def _normalize(info_rows: list[dict]) -> list[dict]:
    out = []
    for r in info_rows:
        out.append({
            "code": r.get("code", ""),
            "name": (r.get("name") or "").replace(" ", ""),
            "board": _board_of(r.get("high_days_value"), r.get("high_days")),
            "high_days": r.get("high_days", ""),
            "first_seal": _to_hms(r.get("first_limit_up_time")),
            "last_seal": _to_hms(r.get("last_limit_up_time")),
            "reason": r.get("reason_type") or "",
            "limit_up_type": r.get("limit_up_type") or "",
            "pct": r.get("change_rate"),
            "market_type": r.get("market_type") or "",
        })
    return out


def fetch_ths_zt(date: str, retries: int = 3, timeout: float = 12.0) -> list[dict]:
    """date: YYYY-MM-DD。返回归一化涨停池。窗口外/限流 → 抛 RuntimeError。"""
    d8 = date.replace("-", "")
    items: list[dict] = []
    page = 1
    while page <= 8:
        url = _POOL_URL.format(page=page, date=d8)
        last_err = None
        for attempt in range(retries):
            try:
                raw = _http(url, timeout=timeout, headers=THS_UA)
                data = json.loads(raw)
                if data.get("status_code") == 0:
                    body = data.get("data") or {}
                    info = body.get("info") or []
                    items.extend(info)
                    total = (body.get("page") or {}).get("total") or 0
                    if len(items) >= total or not info:
                        return _normalize(items)
                    page += 1
                    break
                last_err = data.get("status_msg") or "unknown"
            except Exception as e:  # noqa: BLE001
                last_err = f"{type(e).__name__}: {e}"
            time.sleep(1.2 * (attempt + 1))
        else:
            raise RuntimeError(f"{date} 拉取失败: {last_err}")
        time.sleep(0.35)
    return _normalize(items)


def trade_dates(start: str, end: str) -> list[str]:
    """用上证日K取 [start, end] 交易日（升序）。end 为空取最新。"""
    rows, _ = fetch_daily("sh000001", count=400)
    dates = [r["date"] for r in rows]
    return [d for d in dates if (not start or d >= start) and (not end or d <= end)]


def cache_path(date: str) -> str:
    return os.path.join(CACHE, date.replace("-", "") + ".json")


def load_cached(date: str) -> list[dict] | None:
    p = cache_path(date)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else "2025-08-18"
    end = sys.argv[2] if len(sys.argv) > 2 else ""
    os.makedirs(CACHE, exist_ok=True)
    dates = trade_dates(start, end)
    print(f"窗口 {start}~{end or 'now'}：{len(dates)} 个交易日，缓存至 {CACHE}")
    missing, fail = [], []
    for i, d in enumerate(dates):
        if load_cached(d) is not None:
            continue
        try:
            rows = fetch_ths_zt(d)
            if not rows:
                missing.append(d)  # 空池也可能是非交易日外的缺口，记录
            with open(cache_path(d), "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False)
            top = max((r["board"] for r in rows), default=0)
            print(f"[{i+1}/{len(dates)}] {d} 涨停{len(rows)} 最高{top}板", flush=True)
        except Exception as e:  # noqa: BLE001
            fail.append((d, str(e)))
            print(f"[{i+1}/{len(dates)}] {d} 失败: {e}", flush=True)
        time.sleep(0.3)
    print(f"\n完成：成功 {len(dates)-len(fail)}，记录失败 {len(fail)}，空池 {len(missing)}")
    if fail:
        for d, e in fail[:20]:
            print(f"  {d}: {e}")


if __name__ == "__main__":
    main()
