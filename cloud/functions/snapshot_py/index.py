# -*- coding: utf-8 -*-
"""每日分析快照计算（Python）——被 Node 云函数 daily_job / api 调用。

只负责"算"，返回 JSON 字符串；写库由调用方（Node SDK）完成。
event: {"date": "YYYY-MM-DD"(可选), "mode": "auto"(默认)|"force", "cores": true}

约定：
  mode=auto  → 先判断今天(北京时间)是否为交易日（上证K线最后一根日期==今天），非交易日直接 skip
  mode=force → 跳过交易日判断（用于补跑/调试）
"""
import datetime as _dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from quant.data.kline import fetch_daily                      # noqa: E402
from quant.report.snapshot import build_snapshot              # noqa: E402


def now_cn() -> str:
    """云函数系统时区为 UTC，统一换算北京时间。"""
    return (_dt.datetime.utcnow() + _dt.timedelta(hours=8)).strftime("%Y-%m-%d")


def is_trade_day(today_cn: str) -> tuple:
    """上证日K最后一根日期 == 今天 → 交易日。返回 (bool, last_date)。"""
    try:
        rows, _ = fetch_daily("sh000001", count=5)
        last = rows[-1]["date"] if rows else None
        return (last == today_cn), last
    except Exception as e:
        return False, f"err:{type(e).__name__}:{e}"


def stock_query(code: str, full: bool = False) -> dict:
    """个股异动体检：3/10/30日偏离值 + 严重异动余量；full=true 时补核心评分。"""
    from quant.data.kline import benchmark_index, fetch_daily, normalize_code, prev_trade_date
    from quant.data.pools import fetch_zt_pool
    from quant.indicators.abnormal import compute_deviation
    from quant.indicators.core_score import score_core
    from quant.indicators.sentiment import compute_sentiment
    from quant.regime.cycle import classify

    code = normalize_code(code)
    bcode = benchmark_index(code)
    rows, name = fetch_daily(code, count=80)
    if not rows:
        return {"ok": False, "error": f"无行情数据: {code}"}
    br, bn = fetch_daily(bcode, count=80)
    dev = compute_deviation(rows, br, code, name=name or code,
                            bench_code=bcode, bench_name=bn or bcode)
    out = {
        "ok": True,
        "code": code,
        "name": name or code,
        "bench": bcode,
        "bench_name": bn or bcode,
        "last_date": rows[-1]["date"],
        "last_close": rows[-1]["close"],
        "klines": [{"d": r["date"], "c": r["close"]} for r in rows[-30:]],
        "dev": {
            "dev_3d": dev.dev_3d, "dev_10d": dev.dev_10d, "dev_30d": dev.dev_30d,
            "stock_3d": dev.stock_3d, "stock_10d": dev.stock_10d, "stock_30d": dev.stock_30d,
            "serious_10d_up": dev.serious_10d_up, "serious_30d_up": dev.serious_30d_up,
            "serious_10d_down": dev.serious_10d_down, "serious_30d_down": dev.serious_30d_down,
            "headroom_10d_up": dev.headroom_10d_up, "headroom_30d_up": dev.headroom_30d_up,
            "headroom_10d_down": dev.headroom_10d_down, "headroom_30d_down": dev.headroom_30d_down,
            "normal_3d_triggered": dev.normal_3d_triggered,
            "same_dir_up_count": dev.same_dir_up_count,
            "same_dir_down_count": dev.same_dir_down_count,
            "near_serious": dev.near_serious,
            "risk_level": getattr(dev, "risk_level", None),
            "limit_pct": dev.limit_pct,
            "notes": list(dev.notes or []),
        },
    }
    if not full:
        return out

    # full：补当日涨停池匹配 + 核心评分（口径与日快照一致）
    try:
        d = rows[-1]["date"]
        zt = fetch_zt_pool(d.replace("-", ""))
        hit = next((x for x in zt if normalize_code(x["code"]) == code), None)
        out["in_zt_pool"] = bool(hit)
        out["board"] = int(hit.get("board_cnt") or 1) if hit else 0
        out["industry"] = (hit or {}).get("industry") or ""
        cur = compute_sentiment(date=d, need_premium=False)
        cyc = classify(cur, None)
        out["market"] = {"date": d, "heat": cur.heat, "band": cur.band,
                         "stage": cyc.stage, "max_board": cur.max_board}
        if hit:
            idx_rows, _ = fetch_daily("sh000001", count=30)
            yday = prev_trade_date(idx_rows, asof=d)
            prev_zt = fetch_zt_pool(yday.replace("-", "")) if yday else []
            sc = score_core(hit, zt, rows, market_max_board=cur.max_board,
                            stage=cyc.stage, heat=cur.heat, prev_zt=prev_zt or None, dev=dev)
            out["score"] = {
                "total": sc.total, "grade": sc.grade, "state": sc.state,
                "sub_a": sc.sub_a, "sub_b": sc.sub_b, "risk_total": sc.risk_total,
                "risk_items": [{"name": t, "score": p, "desc": d2}
                               for (t, p, d2) in (sc.risk_items or [])],
                "signals": list(sc.signals or []),
                "notes": list(sc.notes or []),
            }
    except Exception as e:
        out["score_error"] = f"{type(e).__name__}: {e}"
    return out


def apply_calib(snap: dict, event: dict) -> dict:
    """滚动校准（P4）：接收 calib_rows（历史四元组，不含当日）+ 冻结 lu_min，
    从快照的 ths_tags 取当日三元组 (lu,mb,conn) 后整体重放 evaluate_rows。

    - 与 2026-09-02 P4 基线同源同口径（原函数重放，零漂移），纯函数幂等；
    - ths_tags 抓取失败时今日不并入，返回 ok=False（daily_job 跳过写库，下日补齐窗口）；
    - lu=0 为合法极端值（冰点日），允许并入。
    """
    try:
        from quant.backtest.p4_eval import evaluate_rows
        rows = [dict(r) for r in (event.get("calib_rows") or [])]
        if not rows:
            return {"ok": False, "error": "no calib_rows"}
        d = str(snap.get("date") or "")
        if not d:
            return {"ok": False, "error": "snapshot 无日期"}
        # 防御：只保留早于快照日的历史（补跑/重复触发安全）
        rows = [r for r in rows if str(r.get("d") or "") < d]
        tt = snap.get("ths_tags") or {}
        if not isinstance(tt, dict) or tt.get("error") or str(tt.get("date") or "") != d:
            return {"ok": False, "error": f"ths_tags 不可用: {tt.get('error') if isinstance(tt, dict) else '缺 ths_tags'}",
                    "rows_hist": len(rows)}
        today_row = {"d": d, "lu": int(tt.get("lu") or 0),
                     "mb": int(tt.get("mb") or 1), "conn": int(tt.get("conn") or 0)}
        rows.append(today_row)
        rows.sort(key=lambda r: str(r.get("d") or ""))
        lu_min = event.get("calib_lu_min")
        res = evaluate_rows(rows, lu_min=int(lu_min) if lu_min else None)
        return {"ok": True, "today_row": today_row, "eval": res}
    except Exception as e:
        import traceback
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "trace": traceback.format_exc()[-500:]}


def apply_core_track(snap: dict, event: dict) -> dict:
    """次日表现回填：用今日数据评估昨日核心池，产出晋级/断板与次日涨跌幅。

    - 晋级 adv = 今日仍在涨停池且 板数 > 昨日板数；
    - 次日涨幅 pct = 今日收盘 / 昨日收盘 - 1（K线最后一根必须是快照日，否则置 None）；
    - 纯计算不改快照；daily_job 据此累计各档（S/A/B/C）胜率。
    """
    try:
        from quant.data.kline import fetch_daily
        pend = event.get("prev_cores") or None
        if not pend or not pend.get("items"):
            return {"ok": False, "skipped": "no-pending"}
        d = str(snap.get("date") or "")
        pd = str(pend.get("d") or "")
        # 最终防线：只回填"严格早于快照日"的记录。同日（force 重跑/补跑当天）或未来
        # 记录没有"次日"语义——当日入选即涨停，用同日数据评估会产出脏胜率（adv 恒假）。
        if not pd or pd >= d:
            return {"ok": False, "skipped": "not-yesterday", "prev_date": pd, "date": d}
        # 今日涨停全集（东财池全量，来自 themes.members）：code -> 板数
        board_map: dict = {}
        for th in (snap.get("themes") or []):
            for m in (th.get("members") or []):
                if m.get("code"):
                    board_map[m["code"]] = int(m.get("board") or 1)
        out = []
        for it in pend["items"]:
            code = it.get("code")
            prev_board = int(it.get("board") or 0)
            tb = board_map.get(code)
            in_pool = tb is not None
            pct = None
            try:
                rows, _ = fetch_daily(code, count=3)
                if len(rows) >= 2 and rows[-1].get("date") == d:
                    p0, p1 = rows[-2]["close"], rows[-1]["close"]
                    if p0:
                        pct = round((p1 / p0 - 1) * 100, 2)
            except Exception:
                pct = None
            out.append({
                "code": code, "name": it.get("name"), "grade": it.get("grade"),
                "prev_board": prev_board, "board": tb, "in_pool": in_pool,
                "adv": bool(in_pool and tb > prev_board), "pct": pct,
            })
        return {"ok": True, "date": d, "prev_date": pend.get("d"), "results": out}
    except Exception as e:
        import traceback
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "trace": traceback.format_exc()[-500:]}


def main(event, context):
    event = event or {}
    if isinstance(event, str):
        try:
            event = json.loads(event)
        except Exception:
            event = {}

    # 个股异动体检
    if event.get("action") == "stock":
        code = str(event.get("code") or "").strip()
        if not code:
            return {"ok": False, "error": "缺少 code"}
        try:
            return stock_query(code, full=bool(event.get("full")))
        except Exception as e:
            import traceback
            return {"ok": False, "error": f"{type(e).__name__}: {e}",
                    "trace": traceback.format_exc()[-600:]}

    # 实验室回测：对指定历史日的候选集重算 build_lab（真实六源），供本地回放脚本反推可靠性。
    # 注意：六源与基本面为「当前快照」口径（东财接口按最新披露返回，非严格按入选日历史值），
    # 仅用于 15 交易日窗口的近似可靠性量化；板高/题材/核心等级/verb 为入选日真实值。
    if event.get("action") == "lab_backtest":
        from quant.report.lab import build_lab
        from quant.data.pools import fetch_zt_pool
        d = str(event.get("date") or today_cn)
        codes = [c for c in (event.get("codes") or []) if c.get("code")]
        if not codes:
            return {"ok": False, "error": "缺少 codes"}
        try:
            zt = fetch_zt_pool(d.replace("-", ""))
        except Exception as e:
            return {"ok": False, "error": f"zt pool fail: {e}"}
        cores = [{"code": c.get("code"), "name": c.get("name", ""),
                  "industry": c.get("industry", ""), "grade": c.get("grade"),
                  "board": int(c.get("board") or 1)} for c in codes]
        try:
            # per_stock 透传 verb/in_core/grade，使重算与日快照同源同口径（含 verb 风控罚分）
            lab = build_lab(zt, cores, codes, date=d)
        except Exception as e:
            import traceback
            return {"ok": False, "error": f"build_lab fail: {type(e).__name__}: {e}",
                    "trace": traceback.format_exc()[-500:]}
        scores = {}
        for r in (lab.get("ranks") or []):
            scores[r["code"]] = {"lab": r.get("lab"), "q": r.get("q"), "e": r.get("e"),
                                  "veto": False, "board": r.get("board")}
        for v in (lab.get("vetoed") or []):
            scores[v["code"]] = {"lab": None, "q": None, "e": v.get("e"),
                                  "veto": True, "board": v.get("board"),
                                  "reason": v.get("veto_reason")}
        return {"ok": True, "date": d, "pool_n": lab.get("pool_n"),
                "stage": lab.get("stage"), "scores": scores}

    # 形态块单独重算（供 21:00 夜间任务）：当日龙虎榜约 18:00 后才发布，16:05/16:40
    # 的快照里 pattern.lhb 必为空；夜间用本 action 重算后由 daily_job 只合并
    # snapshot.pattern 一个字段（避免整体 set 覆盖吞字段）。
    if event.get("action") == "pattern_only":
        from quant.data.kline import normalize_code
        from quant.data.pools import fetch_zt_pool
        from quant.indicators.ma_pattern import scan_pattern
        d = str(event.get("date") or today_cn)
        try:
            zt = fetch_zt_pool(d.replace("-", ""))
        except Exception as e:
            return {"ok": False, "error": f"zt pool fail: {type(e).__name__}: {e}"}
        if not zt:
            return {"ok": False, "error": f"涨停池为空（{d} 非交易日或数据未发布）"}
        cmap = {}
        for x in zt:
            c = normalize_code(x.get("code", ""))
            cmap[c] = {"code": c, "name": x.get("name", ""),
                       "board": int(x.get("board_cnt") or 1), "in_core": False}
        for c0 in (event.get("cores") or []):
            c = normalize_code(c0.get("code", ""))
            if c in cmap:
                cmap[c]["in_core"] = True
            else:
                cmap[c] = {"code": c, "name": c0.get("name", ""),
                           "board": int(c0.get("board") or 1), "in_core": True}
        try:
            pat = scan_pattern(list(cmap.values()), date=d,
                               flow_agg=event.get("flow_agg"))
        except Exception as e:
            import traceback
            return {"ok": False, "error": f"scan_pattern fail: {type(e).__name__}: {e}",
                    "trace": traceback.format_exc()[-600:]}
        pat["date"] = d
        return {"ok": True, "date": d, "pattern": pat}

    mode = event.get("mode", "auto")
    date = event.get("date")
    with_cores = event.get("cores", True)
    today_cn = now_cn()

    # 诊断：单独测当日同花顺涨停池抓取（不跑全量快照）
    if event.get("action") == "diag_ths":
        from quant.report.snapshot import _ths_tags_today
        d = str(event.get("date") or today_cn)
        try:
            res = _ths_tags_today(d)
            return {"ok": True, "date": d, "ths_tags": res}
        except Exception as e:
            import traceback
            return {"ok": False, "error": f"{type(e).__name__}: {e}",
                    "trace": traceback.format_exc()[-800:]}

    # 诊断：资金流（多日）+ 龙虎榜 云端可达性。
    # 必要性：本机沙箱对 push2his 的 fflow 路径有拦截（curl 52 / urllib RemoteDisconnected），
    # 多日主力净额只能在云端函数内取到，故必须用本 action 验收，而非本地。
    if event.get("action") == "diag_flow":
        out = {"ok": True, "now_cn": today_cn}
        codes = [str(c) for c in (event.get("codes")
                                  or ["sh600237", "sz300563", "sz000001", "bj920819"])]
        try:
            from quant.data.moneyflow import query_flows
            out["flow"] = query_flows(codes, days=int(event.get("days") or 10))
        except Exception as e:
            import traceback
            out["flow"] = {"error": f"{type(e).__name__}: {e}",
                           "trace": traceback.format_exc()[-600:]}
        try:
            from quant.data.kline import prev_trade_date, fetch_daily
            from quant.data.lhb import fetch_lhb_day
            d = str(event.get("date") or today_cn)
            idx, _ = fetch_daily("sh000001", count=10)
            pd = prev_trade_date(idx, asof=d)
            snap = fetch_lhb_day(d)
            prev_snap = fetch_lhb_day(pd) if pd else None
            out["lhb"] = {
                "date": d, "ok": snap["ok"], "n_codes": snap["n_codes"],
                "n_rows": snap["n_rows"], "errors": snap["errors"],
                "prev_date": pd,
                "prev_n_codes": (prev_snap or {}).get("n_codes"),
                "sample": [
                    {"code": c, "name": v["name"], "net_amt": v["net_amt"],
                     "inst": v["inst"], "n_buy_seat": len(v["seats_buy"]),
                     "n_sell_seat": len(v["seats_sell"]), "reasons": v["reasons"]}
                    for c, v in list(snap["by_code"].items())[:2]
                ],
            }
        except Exception as e:
            import traceback
            out["lhb"] = {"error": f"{type(e).__name__}: {e}",
                          "trace": traceback.format_exc()[-600:]}
        return out

    if mode == "auto":
        ok, last = is_trade_day(today_cn)
        if not ok:
            return {"ok": False, "skipped": True,
                    "reason": f"非交易日或K线未更新（今天 {today_cn} / 上证最后 {last}）"}

    try:
        snap = build_snapshot(date, with_cores=with_cores,
                              hist_heats=event.get("hist_heats"),
                              hist_cores=event.get("hist_cores"),
                              flow_agg=event.get("flow_agg"))
    except Exception as e:
        import traceback
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "trace": traceback.format_exc()[-800:]}

    # 滚动校准（可选）：daily_job 传全量 calib_rows + 冻结 calib_lu_min 时，
    # 在快照 ths_tags 基础上重放自评。结果单独返回（不进 daily 文档）。
    calib = None
    if event.get("calib_rows"):
        calib = apply_calib(snap, event)

    # 核心池次日表现回填（可选）：daily_job 传昨日待回填记录，用今日数据评估
    core_track = None
    if event.get("prev_cores"):
        core_track = apply_core_track(snap, event)

    return {"ok": True, "date": snap.get("date"), "snapshot": snap,
            "calib": calib, "core_track": core_track}
