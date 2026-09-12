# -*- coding: utf-8 -*-
"""云端出网探针 第六轮：摸清「消息面」数据源。

前几轮已验证：东财 F10 股东研究（holders 模式）、若干 datacenter 报表。
本轮要回答：
  1. 公告接口 np-anotice-stock/api/security/ann 的字段结构（title/notice_date/notice_type?）
  2. 个股新闻流 getListInfo 的字段结构（title/showTime/来源）
  3. 时间戳格式（决定「T-1盘后 / T-1盘中 / T盘中」时点判定能否落地）
"""
import json
import ssl
import time
import urllib.request

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
}


def _get(url):
    last = ""
    for ctx in (ssl.create_default_context(), ssl._create_unverified_context()):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                return resp.read(), ""
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, e)
    return None, last


def _body(raw):
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk", "replace")


def _dump(tag, url):
    raw, err = _get(url)
    if raw is None:
        return {tag: {"ok": False, "err": err}}
    body = _body(raw)
    if not body.strip():
        return {tag: {"ok": False, "err": "empty body"}}
    try:
        j = json.loads(body)
    except Exception as e:
        # 可能是 jsonp
        s = body.strip()
        if s and (s[0] in "([") is False and "(" in s:
            try:
                j = json.loads(s[s.index("(") + 1:s.rindex(")")])
            except Exception:
                return {tag: {"ok": False, "err": "parse: %s; head=%s" % (e, body[:120])}}
        else:
            return {tag: {"ok": False, "err": "parse: %s; head=%s" % (e, body[:120])}}
    # 找到列表：常见 data.list / data.list[]
    data = j.get("data") if isinstance(j, dict) else None
    lst = None
    if isinstance(data, dict):
        for k in ("list", "ann_list", "list_data"):
            if isinstance(data.get(k), list):
                lst = data[k]
                break
    if lst is None and isinstance(data, list):
        lst = data
    if lst is None and isinstance(j, dict):
        for k in ("list", "data"):
            if isinstance(j.get(k), list):
                lst = j[k]
                break
    if not lst:
        return {tag: {"ok": True, "len": len(body), "top_keys": sorted(j.keys())[:12],
                      "data_type": type(data).__name__,
                      "data_keys": sorted(data.keys())[:12] if isinstance(data, dict) else None,
                      "n": 0}}
    item = lst[0]
    keep = ("title", "notice_date", "notice_type", "showTime", "display_time",
            "mediaName", "columns", "art_code", "codes", "date", "time")
    head3 = []
    for it in lst[:3]:
        row = {}
        for k, v in it.items():
            if k in keep and v:
                row[k] = v
        if not row:
            row = {k: it.get(k) for k in list(it.keys())[:8]}
        head3.append(row)
    return {tag: {"ok": True, "len": len(body), "n": len(lst),
                  "item_keys": sorted(item.keys())[:20], "head3": head3}}




NEWS_URLS = [
    ("f10_news", "https://emweb.securities.eastmoney.com/PC_HSF10/NewsBulletin/PageAjax?code=SH%s"),
    ("list_n0", "https://np-listapi.eastmoney.com/comm/web/getListInfo?client=web&mTypeAndCode=0.%s&type=1&pageSize=20"),
    ("list_n1", "https://np-listapi.eastmoney.com/comm/web/getListInfo?cfh=1&client=web&mTypeAndCode=0.%s&type=1&pageSize=20&fields=code,showTime,title,mediaName,url"),
    ("search", "https://search-api-web.eastmoney.com/search/jsonp?cb=jQuery&param=%s"),
]


def news_r2(code):
    out = {}
    for tag, tpl in NEWS_URLS:
        u = tpl % code
        if tag == "search":
            import urllib.parse
            param = {"uid": "", "keyword": code + " 新闻", "type": ["cfhplk"] if False else ["cfhplk"],
                     "client": "web", "clientType": "web", "clientVersion": "curr",
                     "param": {"cfhplk": {"pageSize": 10, "pageIndex": 1}}}
            u = ("https://search-api-web.eastmoney.com/search/jsonp?cb=cb&param="
                 + urllib.parse.quote(json.dumps({"uid": "", "keyword": code,
                     "type": ["cfhplk"], "client": "web", "clientType": "web",
                     "clientVersion": "curr",
                     "param": {"cfhplk": {"pageSize": 10, "pageIndex": 1}}}, ensure_ascii=False)))
        out.update(_dump(tag, u))
    return out




def news_r3(code):
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/NewsBulletin/PageAjax?code=SH%s" % code
    raw, err = _get(url)
    if raw is None:
        return {"r3": {"ok": False, "err": err}}
    try:
        j = json.loads(_body(raw))
    except Exception as e:
        return {"r3": {"ok": False, "err": "parse: %s head=%s" % (e, _body(raw)[:150])}}
    out = {"r3": {"ok": True, "top": sorted(j.keys())}}
    for key in ("gsgg", "gszx"):
        v = j.get(key)
        if isinstance(v, dict):
            info = {"dict_keys": sorted(v.keys())[:12]}
            for sub in v:
                sv = v[sub]
                if isinstance(sv, dict):
                    info[sub] = {"dict_keys": sorted(sv.keys())[:14]}
                    for s2 in sv:
                        s2v = sv[s2]
                        if isinstance(s2v, list) and s2v and isinstance(s2v[0], dict):
                            info[sub][s2] = {"n": len(s2v), "keys": sorted(s2v[0].keys()),
                                             "head": [{k: it.get(k) for k in list(it.keys())[:9]}
                                                      for it in s2v[:3]]}
                        elif isinstance(s2v, dict):
                            info[sub][s2] = {"keys2": sorted(s2v.keys())[:14]}
                elif isinstance(sv, list) and sv and isinstance(sv[0], dict):
                    info[sub] = {"n": len(sv), "keys": sorted(sv[0].keys()),
                                 "head": [{k: it.get(k) for k in list(it.keys())[:10]}
                                          for it in sv[:4]]}
                else:
                    info[sub] = type(sv).__name__
            out["r3"][key] = info
        elif isinstance(v, list):
            out["r3"][key] = {"n": len(v),
                              "keys": sorted(v[0].keys()) if v else [],
                              "head": [{k: it.get(k) for k in list(it.keys())[:10]}
                                       for it in v[:4]]}
        else:
            out["r3"][key] = type(v).__name__
    return out


def main(event, context):
    code = str((event or {}).get("code") or "600410")
    if (event or {}).get("mode") == "news_r3":
        out = {"now": "probe-v6r3"}
        try:
            out.update(news_r3(code))
        except Exception as e:
            import traceback
            out["r3"] = {"ok": False, "err": traceback.format_exc()[-400:]}
        return out
    if (event or {}).get("mode") == "news_r2":
        out = {"now": "probe-v6r2", "code": code}
        out.update(news_r2(code))
        return out
    ts = int(time.time() * 1000)
    urls = [
        ("ann", "https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=30"
                "&page_index=1&ann_type=A&client_source=web&stock_list=%s&f_node=0&s_node=0" % code),
        ("ann_b", "https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=30"
                  "&page_index=1&ann_type=A&client_source=web&stock_list=%s&f_node=1&s_node=0" % code),
        ("news_a", "https://np-listapi.eastmoney.com/comm/web/getListInfo?cfh=1&client=web"
                   "&mTypeAndCode=0.%s&type=1&pageSize=20&req_trace=%d" % (code, ts)),
        ("news_b", "https://np-listapi.eastmoney.com/comm/web/getListInfo?cfh=1&client=web"
                   "&mTypeAndCode=0.%s&type=0&pageSize=20&req_trace=%d" % (code, ts)),
        ("news_c", "https://np-listapi.eastmoney.com/comm/web/getListInfo?cfh=1&client=web"
                   "&mTypeAndCode=%s&type=1&pageSize=20&req_trace=%d" % (code, ts)),
    ]
    out = {"now": "probe-v6", "code": code}
    for tag, u in urls:
        out.update(_dump(tag, u))
    return out
