# -*- coding: utf-8 -*-
"""消息面定性（「上涨逻辑」模块，2026-09-12 新增）。

对**信号票**（突破 + 粘合观察，约 75 只）抓 T-1 与 T 两天的消息面，
用「性质 × 时点」双维定性，回答三个问题：故事是什么？什么时候讲的？有没有雷？

标签体系（4+1 简洁版，宁缺勿滥）：
  利好·公告  公司公告硬信息（业绩预增/中标/并购/回购/涨价…）
  题材·共振  行业/个股相关新闻在窗口内（蹭热点，看板块持续性）
  资金·独行  窗口内无公告无新闻（最"干净"的技术突破，用席位性质补充谁在买）
  风险·警示  减持/澄清/问询/预亏/质押…（假突破与出货高发区，红灯）
  静默       接口无数据/失败（数据缺失兜底，区别于"无消息"）

时点（判定所依据那条消息的挂网时间，北京时间）：
  T-1盘后 / T-1盘中 / T盘中 / T盘后
  ⚠ T 15:00 收盘后的公告新闻**不参与**利好/题材定性（不影响 T 突破的定价），
    但**风险警示例外**（宁可错杀：T 晚间减持预披露对次日逃命极关键）。

数据源：东财 F10 资讯 ``PC_HSF10/NewsBulletin/PageAjax``（一次请求同时返回
``gsgg`` 公告 + ``gszx`` 公司资讯，与股东研究同域，云端已验证可达）。
- 公告条目：``title`` + ``display_time``（真实挂网时间，"2026-09-03 15:32:38:324"，
  毫秒段用冒号分隔需截断；``notice_date`` 是 T+1 的披露日，**不能**用来判时点）。
- 新闻条目：``gszx.data.items``，``title`` + ``showDateTime``（epoch 毫秒，UTC）。

响应体红线：每票只回压缩摘要（tag/when/why/titles 截 40 字），突破票 ~250B、
粘合票 ~80B，全信号约 9KB —— 远低于嵌套 callFunction ~100KB 截断线。
原始明细不落盘、不入快照文档。
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from quant.data.kline import _http

URL = ("https://emweb.securities.eastmoney.com/PC_HSF10/NewsBulletin/PageAjax?code=%s")
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
       "Referer": "https://emweb.securities.eastmoney.com/"}

WORKERS = 8
_TITLE_MAX = 40          # 标题截断字数
_TITLES_MAX = 3          # 突破票最多带 3 条标题

# 风险关键词（优先级最高；公告与新闻标题都参与）
RISK_KW = ("减持", "清仓", "质押", "澄清", "问询", "立案", "处罚", "违规", "预亏",
           "终止", "解除合同", "冻结", "仲裁", "诉讼", "被诉", "退市", "警示函",
           "监管函", "保留意见", "债务逾期", "失信", "爆雷", "被实施")
# 利好关键词（只用于**公告**标题；新闻不判利好 —— 防止媒体标题党污染定性）
GOOD_KW = ("预增", "扭亏", "预盈", "中标", "框架协议", "并购", "收购", "重组",
           "回购", "增持", "涨价", "提价", "获批", "许可", "专利授权", "补贴",
           "战略合作", "签订", "签署", "中标公告", "订单", "扩产", "满产", "分红")


def _f10_sec(code: str) -> str:
    """sh600410 → SH600410（北交所 PC_HSF10 不覆盖，抓取会失败 → 静默）。"""
    c = str(code or "").lower()
    return ("SH" if c.startswith("sh") else "SZ") + c[2:]


def _parse_cn(s: str) -> str:
    """'2026-09-03 15:32:38:324' → '2026-09-03 15:32:38'（毫秒冒号段截掉）。"""
    return str(s or "")[:19]


def _ms_to_cn(ms) -> str:
    """epoch 毫秒（UTC）→ 北京时间 'YYYY-MM-DD HH:MM:SS'（云端机器是 UTC 时区）。"""
    try:
        import datetime as _dt
        d = _dt.datetime.utcfromtimestamp(int(ms) / 1000.0) + _dt.timedelta(hours=8)
        return d.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError, TypeError):
        return ""


def _slot(dt_cn: str, date: str, prev_date: str) -> str:
    """北京时间字符串 → 时点槽位；不在 [T-1, T] 窗口返回 ''。"""
    if not dt_cn or len(dt_cn) < 16 or not date:
        return ""
    d, hm = dt_cn[:10], dt_cn[11:16]
    if d == date:
        if "09:30" <= hm <= "15:00":
            return "T盘中"
        if hm > "15:00":
            return "T盘后"
        return "T盘前"
    if prev_date and d == prev_date:
        if "09:30" <= hm <= "15:00":
            return "T-1盘中"
        if hm > "15:00":
            return "T-1盘后"
        return "T-1盘前"
    return ""


def _hit(title: str, kws) -> bool:
    t = str(title or "")
    return any(k in t for k in kws)


def fetch_one(code: str):
    """F10 资讯 → (anns, news) 两个原始列表；失败返回 (None, None)。"""
    try:
        j = json.loads(_http(URL % _f10_sec(code), timeout=12, headers=_UA))
    except Exception:
        return None, None
    anns = j.get("gsgg") or []
    data = (j.get("gszx") or {}).get("data") or {}
    news = data.get("items") or []
    if not isinstance(anns, list) or not isinstance(news, list):
        return None, None
    return anns, news


def build_rec(code: str, date: str, prev_date: str, detail: bool) -> dict | None:
    """单票定性。返回压缩摘要 dict；接口失败返回 {"tag": "静默"}。"""
    anns, news = fetch_one(code)
    if anns is None:
        return {"tag": "静默"}

    # 展平成窗口内条目：[(slot, kind, title)]
    items = []
    for a in anns:
        t = str(a.get("title") or "").strip()
        s = _slot(_parse_cn(a.get("display_time")), date, prev_date)
        if t and s:
            items.append((s, "ann", t))
    for n in news:
        t = str(n.get("title") or "").strip()
        s = _slot(_ms_to_cn(n.get("showDateTime")), date, prev_date)
        if t and s:
            items.append((s, "news", t))
    if not items:
        # F10 能通但窗口内无条目（含 F10 空列表）→ 资金·独行
        return {"tag": "资金·独行", "when": "", "why": "", "n": 0}

    # 定性（优先级：风险 > 利好公告 > 题材新闻 > 资金独行）
    # 风险：全窗口（含 T 盘后）公告+新闻都算 —— 宁可错杀
    rep = next(((s, k, t) for s, k, t in items if _hit(t, RISK_KW)), None)
    if rep:
        rec = {"tag": "风险·警示", "when": rep[0], "why": rep[2][:_TITLE_MAX]}
    else:
        preclose = [x for x in items if x[0] not in ("T盘后",)]      # 收盘前窗口
        # 利好：只看**公告**（公司官方行为），T-1盘后挂网是最强组合
        anns_win = [x for x in preclose if x[1] == "ann"]
        rep = next(((s, k, t) for s, k, t in anns_win if _hit(t, GOOD_KW)), None)
        if rep:
            rec = {"tag": "利好·公告", "when": rep[0], "why": rep[2][:_TITLE_MAX]}
        elif any(x[1] == "news" for x in preclose):
            # items 按时间倒序（F10 返回新在前）→ 取窗口内**最新**一条新闻做代表
            first = next((x for x in preclose if x[1] == "news"), preclose[0])
            rec = {"tag": "题材·共振", "when": first[0], "why": first[2][:_TITLE_MAX]}
        else:
            rec = {"tag": "资金·独行", "when": "", "why": ""}
    rec["n"] = len(items)
    if detail:
        # 明细：定性依据那条放首位，其余按 F10 返回序（新在前）补齐
        titles = []
        if rec["tag"] in ("风险·警示", "利好·公告"):
            titles.append(rep[2][:_TITLE_MAX])
        titles.extend(x[2][:_TITLE_MAX] for x in items if x[2] not in titles)
        rec["titles"] = titles[:_TITLES_MAX]
    return rec


def classify_batch(codes: list, date: str, prev_date: str,
                   detail_codes: list | None = None,
                   max_workers: int = WORKERS) -> dict:
    """并发抓一批票的消息面定性。

    返回 ``{code: rec}``；``detail_codes`` 里的票额外带 ``titles``（突破票），
    其余只回标签（粘合观察票）。失败票不进结果（调用方判 None → 前端不渲染）。
    """
    uniq, seen = [], set()
    for c in codes or []:
        k = str(c or "").lower()
        if k and k not in seen:
            seen.add(k)
            uniq.append(k)
    if not uniq or not date:
        return {}
    det = {str(c or "").lower() for c in (detail_codes or [])}

    def work(c):
        try:
            return c, build_rec(c, date, prev_date or "", detail=c in det)
        except Exception:
            return c, None

    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        for c, rec in ex.map(work, uniq):
            if rec:
                out[c] = rec
    return out


if __name__ == "__main__":
    import sys
    ds = sys.argv[1:] or ["sh600410"]
    print(json.dumps(classify_batch(ds, "2026-09-11", "2026-09-10",
                                    detail_codes=ds), ensure_ascii=False, indent=1))
