# -*- coding: utf-8 -*-
"""双线粘合突破（MA7 / MA21）形态扫描。

口径（2026-09-11 定，用户确认）：
- 数据：腾讯日K，**前复权 qfq**（本项目惯例：前复权仅作形态判断）
- 粘合：|MA7 − MA21| / MA21 ≤ 2.5%，且**连续 ≥3 个交易日**
- 突破：当日 **收盘上穿 MA21**（前一日收盘 ≤ MA21）且 **MA7 上翘**
- 量能确认：当日成交量 ≥ 前 5 日均量 × 1.5 —— 作为**确认旗标**，不参与"突破"判定
- 候选池：当日涨停 ∪ 核心池（与 Lab 同池）

说明：本模块会被 CloudBase Python3.7 云函数直接引用，故启用
`from __future__ import annotations` 以兼容 PEP604 写法（X | None）。
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from quant.data.kline import fetch_daily, normalize_code

MA_FAST = 7
MA_SLOW = 21
GLUE_PCT = 0.025      # 粘合阈值：|MA7-MA21|/MA21 ≤ 2.5%
GLUE_DAYS = 3         # 粘合需持续的交易日数
VOL_MULT = 1.5        # 放量确认：成交量 ≥ 前5日均量 × 1.5
MIN_BARS = MA_SLOW + GLUE_DAYS + 3

PARAMS = {
    "ma_fast": MA_FAST,
    "ma_slow": MA_SLOW,
    "glue_pct": GLUE_PCT,
    "glue_days": GLUE_DAYS,
    "vol_mult": VOL_MULT,
    "fq": "qfq",
    "note": "前复权仅作形态判断；量能为确认旗标，不参与突破判定",
}


def _ma(closes: list[float], n: int, i: int):
    """第 i 根（含）的 n 日简单均线；数据不足返回 None。"""
    if i + 1 < n:
        return None
    return sum(closes[i + 1 - n:i + 1]) / float(n)


def _glue(closes: list[float], i: int):
    """返回 (ma7, ma21, 粘合度)；数据不足或 ma21<=0 返回 (None,None,None)。"""
    m7 = _ma(closes, MA_FAST, i)
    m21 = _ma(closes, MA_SLOW, i)
    if m7 is None or m21 is None or m21 <= 0:
        return None, None, None
    return m7, m21, abs(m7 - m21) / m21


def scan_one(item: dict) -> dict | None:
    """扫描单只标的；无信号返回 None。item: {code, name, board, in_core}"""
    code = normalize_code(str(item.get("code") or ""))
    if not code:
        return None

    rows, nm = fetch_daily(code, count=120, fq="qfq")
    if not rows or len(rows) < MIN_BARS:
        return None

    closes = [r["close"] for r in rows]
    vols = [r["volume"] for r in rows]
    i = len(rows) - 1
    d = rows[i]["date"]

    # 粘合布尔序列（索引从 MA_SLOW-1 起才有 MA21）
    glue_ok: dict[int, bool] = {}
    for k in range(MA_SLOW - 1, len(rows)):
        _, _, g = _glue(closes, k)
        glue_ok[k] = bool(g is not None and g <= GLUE_PCT)

    def run_at(k: int) -> int:
        """以 k 为终点向前数连续粘合天数。"""
        n = 0
        while k in glue_ok and glue_ok.get(k):
            n += 1
            k -= 1
        return n

    prev3 = [i - 1, i - 2, i - 3]
    glued_prev = all(glue_ok.get(k) for k in prev3) if (i - 3) >= (MA_SLOW - 1) else False

    m7, m21, glue_now = _glue(closes, i)
    m7p, m21p, _ = _glue(closes, i - 1)
    if m7 is None or m21 is None or m21p is None:
        return None

    close = closes[i]
    prev_close = closes[i - 1]
    pct = (close - prev_close) / prev_close if prev_close else 0.0

    # 突破：当日收盘上穿 MA21 且 MA7 上翘
    breakout = bool(close > m21 and prev_close <= m21p and m7 > m7p)

    # 量能：当日量 / 前5日均量
    base = vols[i - 5:i]
    avg5 = sum(base) / float(len(base)) if base else 0.0
    vol_ratio = (vols[i] / avg5) if avg5 > 0 else None
    vol_ok = bool(vol_ratio is not None and vol_ratio >= VOL_MULT)

    glued_today = bool(glue_now is not None and glue_now <= GLUE_PCT)
    state = ""
    if breakout and glued_prev:
        state = "突破"
    elif glued_today and run_at(i) >= GLUE_DAYS:
        state = "粘合中"

    if not state:
        return None

    return {
        "code": code,
        "name": nm or item.get("name") or "",
        "board": int(item.get("board") or 1),
        "in_core": bool(item.get("in_core")),
        "date": d,
        "state": state,
        "close": round(close, 2),
        "pct": round(pct * 100, 2),
        "ma7": round(m7, 3),
        "ma21": round(m21, 3),
        "glue": round((glue_now or 0) * 100, 2),   # 粘合度 %
        "glue_days": run_at(i) if glued_today else run_at(i - 1),
        "vol_ratio": round(vol_ratio, 2) if vol_ratio else None,
        "vol_ok": vol_ok,
    }


def scan_pattern(cands: list[dict], max_workers: int = 5) -> dict:
    """对候选池并发扫描。返回 {date, scan_n, hit_n, watch_n, hits, watch, params, errors, time_ms}"""
    t0 = time.time()
    hits: list[dict] = []
    watch: list[dict] = []
    errors: list[str] = []

    def work(it):
        try:
            return scan_one(it)
        except Exception as e:  # 单只失败不影响整体
            return {"__err": f"{it.get('code')}: {e}"}

    items = list(cands or [])
    if items:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for r in ex.map(work, items):
                if not r:
                    continue
                if "__err" in r:
                    errors.append(r["__err"])
                    continue
                if r.get("state") == "突破":
                    hits.append(r)
                else:
                    watch.append(r)

    # 突破：放量优先，其次粘合天数长、涨幅大
    hits.sort(key=lambda r: (-(r.get("vol_ratio") or 0), -(r.get("glue_days") or 0), -(r.get("pct") or 0)))
    watch.sort(key=lambda r: (-(r.get("glue_days") or 0), (r.get("glue") or 99)))

    return {
        "scan_n": len(items),
        "hit_n": len(hits),
        "watch_n": len(watch),
        "hits": hits,
        "watch": watch[:30],
        "params": PARAMS,
        "errors": errors[:8],
        "time_ms": int((time.time() - t0) * 1000),
    }
