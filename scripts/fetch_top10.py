#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stock-hots 程序化取数：多平台热门股票榜单 → 综合前十 + 简要 JSON。

纯 HTTP 实现（标准库 only），请求 8 个已验证的平台榜单接口：

  em  = 东财   https://emappdata.eastmoney.com/stockrank/getAllCurrentList     (POST)
  ths = 同花顺 https://eq.10jqka.com.cn/open/api/hot_list/v1/hot_stock/a/hour/data.txt
  kpl = 开盘啦 http://wzslinker.top/companys/api-proxy.php?type=longhuvip&endpoint=get_hot_phb
  tdx = 通达信 http://wzslinker.top/companys/api-proxy.php?type=tdx
  xq  = 雪球   http://wzslinker.top/companys/api-proxy.php?type=xueqiu&size=100&_type=10
  cls = 财联社 http://wzslinker.top/companys/api-proxy.php?type=cls_hot_stock
  tgb = 淘股吧 http://wzslinker.top/companys/api-proxy.php?type=tgb_notice
  dzh = 大智慧 https://imsearch.dzh.com.cn/stock/top?size=100&type=0&time=h

综合口径（与聚合页展示名次可能有差异，属不同算法口径）：
  候选：至少 3 个平台上榜；得分 = 上榜平台名次平均值（越小越热）；
  同分时上榜平台数多的优先；综合前十 = 得分升序取前 10。

输出：
  --json         输出简要 JSON（综合前十 + 各平台 TOP10 + 快照时间）到 stdout
  --json <file>  同时写入文件
  不带 --json    打印人类可读的综合前十列表
"""
import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# 平台元信息：key -> (标签, 采样深度, 默认权重)
PLATFORMS = {
    "em":  ("东财", 100, 1.0),
    "ths": ("同花顺", 100, 1.0),
    "kpl": ("开盘啦", 50, 1.0),
    "tdx": ("通达信", 100, 1.0),
    "xq":  ("雪球", 100, 1.0),
    "cls": ("财联社", 30, 1.0),
    "tgb": ("淘股吧", 50, 1.0),
    "dzh": ("大智慧", 100, 1.0),
}
ORDER = list(PLATFORMS)

URLS = {
    "em":  "https://emappdata.eastmoney.com/stockrank/getAllCurrentList",
    "ths": "https://eq.10jqka.com.cn/open/api/hot_list/v1/hot_stock/a/hour/data.txt?_=1",
    "kpl": "http://wzslinker.top/companys/api-proxy.php?type=longhuvip&endpoint=get_hot_phb",
    "tdx": "http://wzslinker.top/companys/api-proxy.php?type=tdx",
    "xq":  "http://wzslinker.top/companys/api-proxy.php?type=xueqiu&size=100&_type=10&_=1",
    "cls": "http://wzslinker.top/companys/api-proxy.php?type=cls_hot_stock",
    "tgb": "http://wzslinker.top/companys/api-proxy.php?type=tgb_notice&_=1",
    "dzh": "https://imsearch.dzh.com.cn/stock/top?size=100&type=0&time=h&_=1",
}


def fetch_json(url, method="GET", timeout=20):
    if method == "POST":
        req = urllib.request.Request(url, data=b"{}", headers={**UA, "Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    for enc in ("utf-8", "gbk"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    else:
        text = raw.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except Exception:
        # 通达信等返回形如 [[...]] 的 JSON 数组文本
        return json.loads(text.lstrip("\ufeff").strip())


def _code_of(s):
    m = re.search(r"\d{6}", s)
    return m.group(0) if m else s


def parse_em(obj):
    """东财: data=[{sc:'SH603127', rk:1, ...}] 顺序即排名。"""
    out = []
    for i, it in enumerate(obj.get("data") or [], start=1):
        out.append({"code": _code_of(it.get("sc", "")), "name": "", "rank": i})
    return out


def parse_ths(obj):
    """同花顺: data.stock_list=[{order:1, code, name, rate}]"""
    out = []
    for it in (obj.get("data") or {}).get("stock_list") or []:
        out.append({"code": it.get("code", ""), "name": it.get("name", ""), "rank": it.get("order")})
    return out


def parse_kpl(obj):
    """开盘啦: {Day, List:[[code,name,pct,?,rank,0,0],...]} 排名取第5列（idx=4）。"""
    out = []
    for i, it in enumerate(obj.get("List") or [], start=1):
        if len(it) >= 5 and str(it[4]).lstrip("-").isdigit() and int(it[4]) > 0:
            out.append({"code": str(it[0]), "name": str(it[1]), "pct": it[2], "rank": int(it[4])})
        elif len(it) >= 2:
            out.append({"code": str(it[0]), "name": str(it[1]), "pct": it[2] if len(it) > 2 else None, "rank": i})
    return out


def parse_tdx(obj):
    """通达信: [[meta],[header],rows...] header 含 sec_code/stock_name/chg/now_price/ranking"""
    rows = []
    header = None
    for item in obj:
        if not isinstance(item, list) or not item:
            continue
        if isinstance(item[0], str) and "sec_code" in item:
            header = item
        elif isinstance(item[0], str) and item[0].lstrip("-").isdigit():
            rows.append(item)
        else:
            continue  # meta 行（如 [0,"",100,...] 首元素为数字，或其它非数据行）
    idx = {}
    if header:
        for i, h in enumerate(header):
            if h in ("sec_code", "stock_name", "chg", "now_price", "ranking"):
                idx[h] = i
    out = []
    for i, row in enumerate(rows, start=1):
        def g(k):
            j = idx.get(k)
            return row[j] if j is not None and j < len(row) else None
        rank = g("ranking")
        if rank is None or str(rank) == "":
            rank = i
        out.append({
            "code": _code_of(str(g("sec_code") or "")),
            "name": g("stock_name") or "",
            "pct": g("chg"),
            "price": g("now_price"),
            "rank": int(rank),
        })
    return out


def parse_xq(obj):
    """雪球: data.items=[{symbol:'SH603259', code, name, ...}] 顺序即排名。"""
    out = []
    for i, it in enumerate((obj.get("data") or {}).get("items") or [], start=1):
        out.append({"code": it.get("code", _code_of(it.get("symbol", ""))), "name": it.get("name", ""), "rank": i})
    return out


def parse_cls(obj):
    """财联社: data=[{stock:{name, RiseRange, StockID, last}, ranking_change}] 顺序即排名。"""
    out = []
    for i, it in enumerate(obj.get("data") or [], start=1):
        s = it.get("stock") or {}
        out.append({
            "code": _code_of(s.get("StockID", "")),
            "name": s.get("name", "").replace(" ", ""),
            "pct": s.get("RiseRange"),
            "price": s.get("last"),
            "rank": i,
        })
    return out


def parse_tgb(obj):
    """淘股吧: dto=[{fullCode, stockName, ranking, ...}]"""
    out = []
    for it in obj.get("dto") or []:
        out.append({
            "code": _code_of(it.get("fullCode", "")),
            "name": it.get("stockName", ""),
            "rank": it.get("ranking") or len(out) + 1,
        })
    return out


def parse_dzh(obj):
    """大智慧: result=[{SH688185:1140.6}, ...] 顺序即排名。"""
    out = []
    for i, it in enumerate(obj.get("result") or [], start=1):
        for k in it:
            out.append({"code": _code_of(k), "name": "", "rank": i, "score": it[k]})
            break
    return out


PARSERS = {"em": parse_em, "ths": parse_ths, "kpl": parse_kpl, "tdx": parse_tdx,
           "xq": parse_xq, "cls": parse_cls, "tgb": parse_tgb, "dzh": parse_dzh}


def fetch_all(timeout=20):
    """返回 {platform_key: [{'code','name','rank',...}]}，失败平台置空列表。"""
    out = {}
    for key in ORDER:
        try:
            obj = fetch_json(URLS[key], method="POST" if key == "em" else "GET", timeout=timeout)
            out[key] = PARSERS[key](obj)
        except Exception:
            out[key] = []
    return out


def build_ranks(platform_lists):
    """合并为 {code: {'name', 'ranks':{platform: rank}, 'quote':{pct, price}}}"""
    stocks = {}
    for key in ORDER:
        depth = PLATFORMS[key][1]
        for it in platform_lists.get(key) or []:
            code = it.get("code") or ""
            if not code:
                continue
            st = stocks.setdefault(code, {"name": "", "ranks": {}, "quote": {}})
            if not st["name"] and it.get("name"):
                st["name"] = it["name"]
            r = it.get("rank")
            if r and int(r) <= depth:
                st["ranks"][key] = int(r)
            for f in ("pct", "price"):
                v = it.get(f)
                if v not in (None, "") and f not in st["quote"]:
                    st["quote"][f] = v
    return stocks


def score_of(st):
    """（保留：综合口径说明）上榜平台名次平均（越小越热），缺榜平台不计入平均。"""
    ranks = list(st["ranks"].values())
    if not ranks:
        return None
    return sum(ranks) / len(ranks)


def top10(stocks, n=10, min_platforms=3):
    scored = []
    for code, st in stocks.items():
        ranks = list(st["ranks"].values())
        if len(ranks) < min_platforms:
            continue  # 少于 3 个平台上榜的股票不计入综合（防单平台钻空）
        avg = sum(ranks) / len(ranks)
        scored.append((avg, -len(ranks), code))
    scored.sort(key=lambda x: (x[0], x[1]))
    out = []
    for avg, neg_present, code in scored[:n]:
        st = stocks[code]
        present = -neg_present
        parts = {k: st["ranks"].get(k) for k in ORDER}
        present_ranks = [v for v in parts.values() if v is not None]
        best = [PLATFORMS[k][0] for k in ORDER if parts.get(k) is not None and parts[k] == min(present_ranks)]
        out.append({
            "rank": len(out) + 1,
            "code": code,
            "name": st["name"],
            "avg_rank": round(avg, 2),
            "platform_count": present,
            "price": st["quote"].get("price"),
            "pct": st["quote"].get("pct"),
            "platforms": parts,
            "best_platform": best,
        })
    return out


def platform_top(platform_lists, stocks, n=10):
    out = {}
    for key in ORDER:
        label = PLATFORMS[key][0]
        items = []
        for it in (platform_lists.get(key) or [])[:n]:
            st = stocks.get(it.get("code") or "")
            name = it.get("name") or (st["name"] if st else "")
            items.append({"rank": it.get("rank"), "code": it.get("code"), "name": name})
        out[key] = {"label": label, "top": items}
    return out


def now_iso():
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def main():
    ap = argparse.ArgumentParser(description="stock-hots 程序化取数")
    ap.add_argument("--json", nargs="?", const="-", default=None, help="输出简要 JSON（- 或省略参数为 stdout；可跟文件路径）")
    ap.add_argument("--top", type=int, default=10, help="综合前十取前 N（默认 10）")
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()

    platform_lists = fetch_all(timeout=args.timeout)
    stocks = build_ranks(platform_lists)
    top = top10(stocks, n=args.top)
    pt = platform_top(platform_lists, stocks)

    payload = {
        "source": "wzslinker-8-platform-apis",
        "snapshot_time": now_iso(),
        "algorithm": "avg-rank (mean of present platform ranks; more platforms first)",
        "depths": {k: PLATFORMS[k][1] for k in ORDER},
        "top" + str(args.top): top,
        "platform_top": pt,
    }

    if args.json is not None:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.json == "-":
            print(text)
        else:
            with open(args.json, "w", encoding="utf-8") as f:
                f.write(text)
            print("written:", args.json)
    else:
        print("综合前十（%s，上榜平台平均名次口径）" % now_iso())
        for it in top:
            ranks = " ".join("%s:%s" % (PLATFORMS[k][0], v) if v is not None else "%s:-" % PLATFORMS[k][0] for k, v in it["platforms"].items())
            print("%2d  %s  %s  %s" % (it["rank"], it["name"], it["code"], ranks))


if __name__ == "__main__":
    main()
