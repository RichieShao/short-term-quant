# -*- coding: utf-8 -*-
"""每日分析快照（结构化 JSON）——供手机网页分析系统消费。

与 build_report(markdown) 同源同口径，只是输出结构化数据：
  market    / sentiment / series / cycle / themes / cores / actions / ladder

本地与云端共用：
  python3 -m quant.report.snapshot [--date YYYY-MM-DD] [--out x.json]
云函数 daily_snapshot 直接调用 build_snapshot() 后写数据库。
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys

from quant.data.kline import benchmark_index, fetch_daily, fetch_realtime, normalize_code, prev_trade_date
from quant.data.pools import fetch_dt_pool, fetch_zb_pool, fetch_zt_pool
from quant.indicators.abnormal import compute_deviation
from quant.indicators.core_score import score_core
from quant.indicators.ma_pattern import scan_pattern
from quant.indicators.sentiment import compute_sentiment
from quant.regime.cycle import classify
from quant.report.daily import INDEXES, _trade_dates, market_env
from quant.report.lab import build_lab
from quant.rules.actions import build_action_plan

VERSION = "v0.1-P4"


def _f(x, nd=4):
    """浮点安全格式化（None 透传）。"""
    if x is None:
        return None
    try:
        return round(float(x), nd)
    except (TypeError, ValueError):
        return None


def _market(date: str) -> list[dict]:
    """三大指数当日收盘涨跌（历史日按日K算，最新日可用实时）。"""
    out = []
    for code, name in INDEXES:
        try:
            rows, _n = fetch_daily(code, count=8)
            ds = [r["date"] for r in rows]
            if date in ds:
                i = ds.index(date)
                prev_close = rows[i - 1]["close"] if i >= 1 else rows[i]["close"]
                pct = rows[i]["close"] / prev_close - 1.0 if prev_close else 0.0
                out.append({
                    "code": code, "name": name,
                    "pct": _f(pct, 4), "close": _f(rows[i]["close"], 2),
                })
        except Exception:
            continue
    if not out:  # 回退：实时行情
        try:
            rt = fetch_realtime([c for c, _ in INDEXES])
            for code, name in INDEXES:
                v = rt.get(code)
                if v:
                    out.append({"code": code, "name": name,
                                "pct": _f(v["pct"] / 100.0 if abs(v["pct"]) > 1.5 else v["pct"], 4),
                                "close": _f(v.get("price"), 2)})
        except Exception:
            pass
    return out


def _sentiment_payload(s) -> dict:
    return {
        "date": s.date,
        "heat": _f(s.heat, 1),
        "band": s.band,
        "lu": s.lu_count,
        "ld": s.ld_count,
        "zb": s.zb_count,
        "zb_rate": _f(s.zhaban_rate, 4),
        "max_board": s.max_board,
        "conn": s.conn_board_count,
        "premium": _f(s.yest_premium, 4),
        "ladder": {str(k): v for k, v in sorted(s.ladder.items()) if v},
    }


def _ths_tags_today(today: str):
    """当日同花顺涨停池题材计数（与题材生命期聚合同口径，仅收盘后稳定）。

    返回 {"date","lu","mb","conn","counts":{tag:当日家数}}；mb=当日最高连板、
    conn=连板≥2 家数（供滚动校准三元组 (lu,mb,conn) 与题材生命期共用一次抓取）。
    失败时返回带 error 字段的 dict（不阻断快照，但供 api day 可观测化，便于排查云端抓取问题）。
    """
    try:
        from quant.backtest.p4_ths_pool import fetch_ths_zt
        from quant.backtest.theme_life import counts_of_rows
        rows = fetch_ths_zt(today.replace("-", ""))
        boards = [int(x.get("board") or 1) for x in rows]  # THS 池行键为 board（非 board_cnt）
        return {"date": today, "lu": len(rows),
                "mb": max(boards) if boards else 0,
                "conn": sum(1 for b in boards if b >= 2),
                "counts": counts_of_rows(rows)}
    except Exception as e:
        import traceback
        return {"date": today, "error": f"{type(e).__name__}: {e}",
                "trace": traceback.format_exc()[-600:]}


def _themes(zt_today: list[dict]) -> list[dict]:
    """当日题材榜（东财行业粒度，全量）。含成分股 members 供前端点开查看。"""
    agg: dict[str, dict] = {}
    for x in zt_today:
        name = (x.get("industry") or "").strip() or "其他"
        e = agg.setdefault(name, {"name": name, "count": 0, "max_board": 0, "members": []})
        e["count"] += 1
        e["max_board"] = max(e["max_board"], int(x.get("board_cnt") or 1))
        e["members"].append({
            "code": x.get("code", ""),
            "name": x.get("name", ""),
            "board": int(x.get("board_cnt") or 1),
            "pct": (round(x["pct"], 4) if x.get("pct") is not None else None),
            "zttj": (x.get("zttj") or ""),
        })
    return sorted(agg.values(), key=lambda d: (d["count"], d["max_board"]), reverse=True)


def _firstboards(zt_today: list[dict]) -> list[dict]:
    """首板（连板==1）列表，按首封时间升序（前排=日内资金最先点火的方向）。

    作为"刚启动"最前置信号：连板≥2 进入核心池的前一站。
    """
    fb = [x for x in zt_today if int(x.get("board_cnt") or 1) == 1]
    fb.sort(key=lambda x: (x.get("first_seal") if x.get("first_seal") is not None else 999999))
    out = []
    for x in fb:
        out.append({
            "code": x.get("code", ""),
            "name": x.get("name", ""),
            "board": 1,
            "industry": (x.get("industry") or "").strip(),
            "pct": (round(x["pct"], 4) if x.get("pct") is not None else None),
            "first_seal": x.get("first_seal"),
            "zttj": (x.get("zttj") or ""),
        })
    return out


def _firstboard_industries(fb: list[dict]) -> list[dict]:
    """首板行业分布（按个数降序，供前端"首板行业分布"展示）。"""
    agg: dict[str, int] = {}
    for x in fb:
        name = (x.get("industry") or "").strip() or "其他"
        agg[name] = agg.get(name, 0) + 1
    return sorted(({"name": k, "count": v} for k, v in agg.items()),
                  key=lambda d: d["count"], reverse=True)


def _ladder_detail(zt_today: list[dict]) -> list[dict]:
    """连板天梯明细：按连板数(≥2)分组，每组列出当日实际个股（前排=首封最早）。

    与 ladder_text（仅计数）互为补充：ladder_text 给骨架，ladder_detail 给血肉，
    供前端渲染成可点击/可读的真实天梯（含空间龙、中位断层判断）。
    """
    groups: dict[int, list[dict]] = {}
    for x in zt_today:
        bc = int(x.get("board_cnt") or 1)
        if bc < 2:
            continue
        groups.setdefault(bc, []).append({
            "code": x.get("code", ""),
            "name": x.get("name", ""),
            "pct": (round(x["pct"], 4) if x.get("pct") is not None else None),
            "zttj": (x.get("zttj") or ""),
            "industry": (x.get("industry") or "").strip(),
            "first_seal": x.get("first_seal"),
        })
    out = []
    for bc in sorted(groups.keys()):
        items = sorted(groups[bc],
                       key=lambda d: (d["first_seal"] if d["first_seal"] is not None else 999999))
        out.append({"board": bc, "count": len(items), "stocks": items})
    return out


def _reversal_signal(cur, series: list, cyc, fb_today: int) -> dict:
    """冰点反转信号监测（退潮/冰点期专用）。

    系统口径 = 溢价转正 + 首板批量，两者同时出现才触发（不提前抢跑）：
      - 溢价转正：昨涨停今均价 > 0（亏钱效应衰竭的第一手证据）；
      - 首板批量：当日首板家数 ≥ 近5交易日首板均值 × 1.3（资金重新试错）。
    仅在 周期=退潮 或 温度<33（冰点档）时激活监测；首板 5 日均值直接取
    series 里现成的 ladder 分布，零额外请求。
    """
    monitor = bool(cyc.stage == "退潮" or cur.heat < 33)
    premium = cur.yest_premium
    prem_ok = premium is not None and premium > 0
    # 首板家数 = 涨停家数 - 连板家数（ladder 只统计 ≥2 板，故用差值；与 firstboards 等长）
    fb_counts = [max(0, x.lu_count - x.conn_board_count) for x in series[-5:]]
    fb_ma5 = (round(sum(fb_counts) / len(fb_counts), 1) if fb_counts else None)
    fb_ok = bool(fb_ma5 and fb_today >= fb_ma5 * 1.3)
    triggered = bool(monitor and prem_ok and fb_ok)

    if not monitor:
        hint = ""
    elif triggered:
        hint = "冰点反转信号触发：溢价转正 + 首板批量同时出现。可小仓冰点反包试错（≤10-20%），只做第一个带动板块走强的新核心，做错次日走。"
    else:
        miss = []
        if not prem_ok:
            miss.append(f"溢价未转正（{_f(premium, 4) if premium is not None else '缺'}）")
        if not fb_ok:
            miss.append(f"首板未放量（今日 {fb_today} 家 vs 5日均 {fb_ma5}）")
        hint = "等信号，别抢跑：" + "；".join(miss) + "。两者同时出现才动手。"
    return {
        "active": monitor,
        "triggered": triggered,
        "stage": cyc.stage,
        "heat": _f(cur.heat, 1),
        "premium": _f(premium, 4) if premium is not None else None,
        "premium_ok": prem_ok,
        "fb_today": fb_today,
        "fb_ma5": fb_ma5,
        "fb_ok": fb_ok,
        "hint": hint,
    }


def _heat_detail(cur, series: list, hist_heats: list | None = None) -> dict:
    """温度计增强数据：分项拆解 + 动量 + 历史分位（均只做展示，不改变 heat 本身）。"""
    from quant.indicators.sentiment import heat_breakdown, heat_momentum, heat_percentile
    try:
        return {
            "breakdown": heat_breakdown(cur),
            "momentum": heat_momentum(series),
            "percentile": heat_percentile(cur.heat, hist_heats),
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _enrich_cores(cores: list[dict], hist_cores: list | None = None) -> list[dict]:
    """核心池增强标记（纯展示，不改评分/分级）：
      - 题材内地位：同题材内按 (板高, 总分) 排名 → ind_rank / ind_total（龙头=1）
      - 连续在池天数：hist_cores = [{d, codes}]（升序，不含当日）→ streak（今日之前连续在池天数）
    """
    groups: dict[str, list] = {}
    for c in cores:
        groups.setdefault(c.get("industry") or "其他", []).append(c)
    for g in groups.values():
        g.sort(key=lambda x: (-(x.get("board") or 0), -(x.get("total") or 0)))
        for i, c in enumerate(g):
            c["ind_rank"] = i + 1
            c["ind_total"] = len(g)

    hist = sorted((hist_cores or []), key=lambda x: str(x.get("d") or ""))
    for c in cores:
        streak = 0
        for h in reversed(hist):
            if c.get("code") in (h.get("codes") or []):
                streak += 1
            else:
                break
        c["streak"] = streak
    return cores


def build_snapshot(date: str | None = None, with_cores: bool = True,
                   hist_heats: list | None = None,
                   hist_cores: list | None = None) -> dict:
    """生成当日完整分析快照。"""
    if date is None:
        dates = _trade_dates(6)
        today = dates[-1]
    else:
        # 历史回看/补灌：窗口需覆盖目标日之前的 6 个交易日。
        # 8 日窗口仅够回溯约一周；更早日期（如批量补灌 20+ 日前）自动回退到年度窗口。
        dates = [d for d in _trade_dates(8) if d <= date][-6:]
        if not dates:
            dates = [d for d in _trade_dates(260) if d <= date][-6:]
        today = dates[-1] if dates else date

    snap = {
        "date": today,
        # 云函数容器时区为 UTC，统一按北京时间记录（本地跑时偏差 <1 分钟，可接受）
        "generated_at": (_dt.datetime.utcnow() + _dt.timedelta(hours=8)).strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "version": VERSION,
        "env": market_env(today),
        "market": _market(today),
    }

    # 温度序列（近6日）
    series = [compute_sentiment(date=d, need_premium=(i == len(dates) - 1))
              for i, d in enumerate(dates)]
    cur = series[-1]
    cyc = classify(cur, series[-2] if len(series) >= 2 else None)

    snap["sentiment"] = _sentiment_payload(cur)
    # 温度计增强：分项构成 / 动量 / 历史分位（纯展示层，不影响 heat 与 P4 校准基线）
    snap["heat_detail"] = _heat_detail(cur, series, hist_heats)
    snap["series"] = [_sentiment_payload(s) for s in series]
    snap["cycle"] = {
        "stage": cyc.stage,
        "trend": cyc.trend,
        "reasons": list(cyc.reason),
        "tone": {
            "启动": "试仓低位新核心，冰点反包首板重点跟踪",
            "发酵": "围绕题材核心/分支核心做多，分歧低吸",
            "高潮": "只做总龙不加仓，中位补涨坚决不接力，盯监管动作",
            "震荡": "核心高抛低吸，等待方向选择，减少无效交易",
            "退潮": "空仓为主，等待亏钱效应衰竭后的冰点反转信号",
        }.get(cyc.stage, ""),
    }
    snap["ladder_text"] = "  ".join(
        f"{k}板×{v}" for k, v in sorted(cur.ladder.items()) if v)

    # 当日/昨日涨停池
    zt_today: list[dict] = []
    prev_zt: list[dict] = []
    try:
        zt_today = fetch_zt_pool(today.replace("-", ""))
        idx_rows, _ = fetch_daily("sh000001", count=30)
        yday = prev_trade_date(idx_rows, asof=today)
        if yday:
            prev_zt = fetch_zt_pool(yday.replace("-", ""))
    except Exception as e:
        snap.setdefault("errors", []).append(f"涨停池获取失败: {e}")

    snap["themes"] = _themes(zt_today)

    # 首板（连板==1）：更前置的"刚启动"信号，按首封时间升序
    fb = _firstboards(zt_today)
    snap["firstboards"] = fb
    snap["firstboards_industry"] = _firstboard_industries(fb)

    # 冰点反转信号监测（退潮/冰点期自动激活，其余期 active=False）
    try:
        snap["reversal"] = _reversal_signal(cur, series, cyc, len(fb))
    except Exception as e:
        snap.setdefault("errors", []).append(f"反转信号计算失败: {e}")
        snap["reversal"] = {"active": False, "error": str(e)}

    # 连板天梯明细（≥2 板，每层实际个股）—— 前端渲染真实天梯
    snap["ladder_detail"] = _ladder_detail(zt_today)

    # 高标：核心评分 + 异动体检（2026-09-07 并发化：涨停爆发日 12 只串行拉 K 线曾使
    # 快照 >23s 触顶 daily_job 调用超时 → 基准预取后 5 线程并发，保序输出）
    cores: list[dict] = []
    sc_objs: list = []          # 复用给动作矩阵，避免二次拉K线
    if with_cores:
        from concurrent.futures import ThreadPoolExecutor
        leaders = sorted((x for x in cur.leaders if x["board"] >= 2),
                         key=lambda d: d["board"], reverse=True)[:12]
        # 基准K线预取（并发前完成，消除共享 cache 竞态）
        bench_cache: dict[str, tuple] = {}
        for ld in leaders:
            bcode = benchmark_index(normalize_code(ld["code"]))
            if bcode not in bench_cache:
                try:
                    bench_cache[bcode] = fetch_daily(bcode, count=80)
                except Exception:
                    bench_cache[bcode] = ([], None)

        def _score_one(ld: dict):
            """单只高标：对齐当日涨停池原行 → 拉K线 → 异动体检 → 核心评分。线程安全（只读共享）。"""
            src = next((x for x in zt_today if x["code"] == ld["code"]), None)
            ld2 = src or ld
            code = normalize_code(ld2["code"])
            bcode = benchmark_index(code)
            try:
                stock_rows, name = fetch_daily(code, count=80)
            except Exception:
                return None
            br, _bn = bench_cache[bcode]
            dev = None
            try:
                dev = compute_deviation(stock_rows, br, code, name=ld2["name"],
                                        bench_code=bcode, bench_name=_bn or bcode)
            except Exception:
                dev = None
            try:
                sc = score_core(ld2, zt_today, stock_rows, market_max_board=cur.max_board,
                                stage=cyc.stage, heat=cur.heat,
                                prev_zt=prev_zt or None, dev=dev)
            except Exception:
                sc = None
            if sc is None:
                return None
            return sc, dev, ld2

        results = []
        with ThreadPoolExecutor(max_workers=5) as _ex:
            results = list(_ex.map(_score_one, leaders))
        for r in results:
            if r is None:
                continue
            sc, dev, ld = r
            sc_objs.append(sc)
            cores.append({
                "code": sc.code,
                "name": sc.name,
                "board": sc.board_cnt,
                "industry": sc.industry,
                # 容量维度（仓位依据）+ 连板轨迹（N天M板）：取自当日涨停池原行
                "amount": ld.get("amount"),
                "float_cap": ld.get("float_cap"),
                "turnover": ld.get("turnover"),
                "zttj": ld.get("zttj") or "",
                "total": _f(sc.total, 1),
                "grade": sc.grade,
                "state": sc.state,
                "sub_a": _f(sc.sub_a, 1),
                "sub_b": _f(sc.sub_b, 1),
                "risk_total": _f(sc.risk_total, 1),
                "detail_a": {
                    "drive": _f(sc.a_drive, 1), "init": _f(sc.a_init, 1),
                    "pop": _f(sc.a_pop, 1), "passive": _f(sc.a_passive, 1),
                },
                "detail_b": {
                    "ladder": _f(sc.b_ladder, 1), "node": _f(sc.b_node, 1),
                    "logic": _f(sc.b_logic, 1),
                },
                "risk_items": [{"name": t, "score": _f(p, 1), "desc": d}
                               for (t, p, d) in (sc.risk_items or [])],
                "signals": list(sc.signals or []),
                "notes": list(sc.notes or []),
                "dev": ({
                    "dev_3d": _f(dev.dev_3d, 4),
                    "dev_10d": _f(dev.dev_10d, 4),
                    "dev_30d": _f(dev.dev_30d, 4),
                    "headroom_10d_up": _f(getattr(dev, "headroom_10d_up", None), 4),
                    "headroom_30d_up": _f(getattr(dev, "headroom_30d_up", None), 4),
                    "serious_10d_up": bool(getattr(dev, "serious_10d_up", False)),
                    "serious_30d_up": bool(getattr(dev, "serious_30d_up", False)),
                    "near_serious": bool(getattr(dev, "near_serious", False)),
                    "risk_level": getattr(dev, "risk_level", None),
                    "bench_name": getattr(dev, "bench_name", None),
                    "last_date": getattr(dev, "last_date", None),
                } if dev else None),
            })
    snap["cores"] = _enrich_cores(cores, hist_cores)

    # 动作清单：复用上面已算出的 CoreScore 对象（不再二次拉K线，云端省时）
    plan = None
    try:
        plan = build_action_plan(cyc, sc_objs, date=today,
                                 market_max_board=cur.max_board,
                                 lu_count=cur.lu_count, zb_count=cur.zb_count)
    except Exception as e:
        snap.setdefault("errors", []).append(f"动作矩阵失败: {e}")

    if plan is not None:
        snap["actions"] = {
            "stage": plan.stage,
            "tone": plan.tone,
            "rules": list(plan.rules or []),
            "watch": list(plan.watch or []),
            "per_stock": [{
                "code": a.code, "name": a.name, "board": a.board_cnt,
                "grade": a.grade, "total": _f(a.total, 1), "state": a.state,
                "verb": a.verb, "position": a.position, "memo": a.memo,
            } for a in plan.per_stock],
        }
    else:
        snap["actions"] = {"stage": cyc.stage, "tone": "", "rules": [], "watch": [],
                           "per_stock": []}

    # 分析系统·实验室（Lab）：每日收盘自动跑，候选=全部题材成分∪核心池。
    # 轻量基本面为"当前快照"口径，仅快照日==全局最新交易日时计算，历史日期跳过（防口径失真）。
    try:
        per_stock = (snap.get("actions") or {}).get("per_stock") or []
        lab = None
        if date is None:  # 每日路径：today 即全局最新交易日
            lab = build_lab(zt_today, cores, per_stock, date=today, stage=cyc.stage)
        else:
            gl = _trade_dates(6)
            if gl and today == gl[-1]:
                lab = build_lab(zt_today, cores, per_stock, date=today, stage=cyc.stage)
        if lab is not None:
            lab["date"] = today
        snap["lab"] = lab
    except Exception as e:
        snap.setdefault("errors", []).append(f"实验室(Lab)失败: {e}")
        snap["lab"] = None

    # 双线粘合突破（MA7/MA21）：候选池同 Lab（当日涨停 ∪ 核心池）。
    # 仅"快照日==全局最新交易日"时扫描——历史/补跑跳过（K线形态只对最新日有决策意义）。
    try:
        is_latest = date is None
        if not is_latest:
            _gl = _trade_dates(6)
            is_latest = bool(_gl and today == _gl[-1])
        pat = None
        if is_latest:
            _cmap: dict[str, dict] = {}
            for x in zt_today:
                c = normalize_code(x.get("code", ""))
                _cmap[c] = {"code": c, "name": x.get("name", ""),
                            "board": int(x.get("board_cnt") or 1), "in_core": False}
            for c0 in cores or []:
                c = normalize_code(c0.get("code", ""))
                if c in _cmap:
                    _cmap[c]["in_core"] = True
                else:
                    _cmap[c] = {"code": c, "name": c0.get("name", ""),
                                "board": int(c0.get("board") or 1), "in_core": True}
            pat = scan_pattern(list(_cmap.values()))
            pat["date"] = today
        snap["pattern"] = pat
    except Exception as e:
        snap.setdefault("errors", []).append(f"形态扫描(双线粘合)失败: {e}")
        snap["pattern"] = None

    # 题材生命期：仅"快照日==全局最新交易日"时抓当日同花顺题材计数，
    # 供 daily_job 增量写入 themelife 聚合（历史/补跑不重复抓取）。
    snap["ths_tags"] = None
    try:
        is_latest = date is None
        if not is_latest:
            gl = _trade_dates(6)
            is_latest = bool(gl and today == gl[-1])
        if is_latest:
            snap["ths_tags"] = _ths_tags_today(today)
    except Exception as e:
        snap.setdefault("errors", []).append(f"题材生命期采集失败: {e}")
        snap["ths_tags"] = None

    return snap


def main():
    args = [a for a in sys.argv[1:]]
    date = None
    out = None
    for i, a in enumerate(args):
        if a == "--date" and i + 1 < len(args):
            date = args[i + 1]
        elif a == "--out" and i + 1 < len(args):
            out = args[i + 1]
    snap = build_snapshot(date)
    text = json.dumps(snap, ensure_ascii=False, indent=2)
    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"已保存 {os.path.abspath(out)}  ({len(text)/1024:.1f} KB)")
    else:
        print(text)
    return snap


if __name__ == "__main__":
    main()
