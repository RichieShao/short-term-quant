# -*- coding: utf-8 -*-
"""云端出网探针 第三轮：确认完整数据链路（三池 + 批量实时 + 个股K线）。"""
import json
import ssl
import urllib.request

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://gu.qq.com/",
}

EM_UT = "7eea3edcaed734bea9cbfc24409ed989"
D = "20260902"

TESTS = [
    ("em_zt", f"https://push2ex.eastmoney.com/getTopicZTPool?ut={EM_UT}&dpt=wz.ztzt"
              f"&Pageindex=0&pagesize=200&sort=fbt%3Aasc&date={D}"),
    ("em_dt", f"https://push2ex.eastmoney.com/getTopicDTPool?ut={EM_UT}&dpt=wz.ztzt"
              f"&Pageindex=0&pagesize=200&sort=fund%3Aasc&date={D}"),
    ("em_zb", f"https://push2ex.eastmoney.com/getTopicZBPool?ut={EM_UT}&dpt=wz.ztzt"
              f"&Pageindex=0&pagesize=200&sort=zbc%3Adesc&date={D}"),
    ("tx_kline_stock", "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
                       "?param=sh600589,day,,,80,qfq"),
    ("tx_kline_idx", "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
                     "?param=sz399102,day,,,80,"),
    ("tx_rt_batch", "https://qt.gtimg.cn/q=" + ",".join(
        [f"sh60{i:04d}" for i in range(10)] + [f"sz00{i:04d}" for i in range(10)])),
]


def main(event, context):
    out = {"results": {}}
    ctx_insec = ssl._create_unverified_context()
    for key, url in TESTS:
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=15,
                                        context=ssl.create_default_context()) as resp:
                raw = resp.read()
        except Exception:
            try:
                req = urllib.request.Request(url, headers=UA)
                with urllib.request.urlopen(req, timeout=15, context=ctx_insec) as resp:
                    raw = resp.read()
            except Exception as e:
                out["results"][key] = {"ok": False, "err": f"{type(e).__name__}: {e}"}
                continue
        # 腾讯实时为 GBK
        try:
            body = raw.decode("utf-8")
        except UnicodeDecodeError:
            body = raw.decode("gbk", "replace")
        rec = {"ok": True, "len": len(body)}
        if key.startswith("em_"):
            try:
                j = json.loads(body)
                pool = ((j.get("data") or {}).get("pool")) or []
                rec["rc"] = j.get("rc")
                rec["tc"] = (j.get("data") or {}).get("tc")
                rec["n"] = len(pool)
                rec["sample"] = {k: pool[0].get(k) for k in
                                 ("c", "n", "lbc", "fbt", "zbc", "hybk", "zdp")} if pool else None
            except Exception as e:
                rec["parse_err"] = str(e)
        elif key.startswith("tx_kline"):
            try:
                j = json.loads(body)
                node = list((j.get("data") or {}).values())[0]
                rows = node.get("qfqday") or node.get("day") or []
                rec["n"] = len(rows)
                rec["last"] = rows[-1][:5] if rows else None
            except Exception as e:
                rec["parse_err"] = str(e)
        else:
            rec["n"] = body.count("~")
            rec["head"] = body[:100]
        out["results"][key] = rec
    return out
