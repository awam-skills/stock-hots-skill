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

数据源配置（sources.json，可缺省）：
  优先读取脚本上级目录的 sources.json（--config 可指定其它路径）：
    urls              覆盖内置接口地址（key 同上表）
    disabled          禁用指定平台（不请求、不进综合）
    aggregator_page   聚合页兜底入口
  配置缺省或键缺失时回落内置默认（DEFAULT_URLS）。

失效自检：
  --check  逐平台探测接口连通性与解析行数，并探活聚合页；
           任一启用平台 FAIL/解析为空或聚合页不可达时退出码 1（禁用平台不计）。

输出：
  --json         输出简要 JSON（综合前十 + 各平台 TOP10 + 快照时间）到 stdout
  --json <file>  同时写入文件
  不带 --json    打印人类可读的综合前十列表（末尾明确上报不可用/禁用平台）
"""
import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

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

CONFIG_FILENAME = "sources.json"
DEFAULT_AGGREGATOR_PAGE = "http://wzslinker.top/companys/情绪为王-01八一热榜.html"

# 状态值：ok / disabled / empty / fail: <原因>
_STATUS_ZH = {"disabled": "已禁用", "empty": "解析为空"}


def load_sources_config(path=None):
    """读取数据源配置，返回 (urls, disabled, aggregator_page, cfg_path)。

    - path 为空时探测 `脚本上级目录/sources.json`，存在才读，否则全部用内置默认；
    - urls 只接受已知平台 key 的覆盖，未知 key 告警并忽略；
    - 解析失败时告警并回落内置默认（不让坏配置直接打断取数）。
    """
    cfg_path = Path(path) if path else Path(__file__).resolve().parent.parent / CONFIG_FILENAME
    urls = dict(URLS)
    disabled = set()
    aggregator_page = DEFAULT_AGGREGATOR_PAGE
    if cfg_path.is_file():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print("warn: %s 解析失败（%s），使用内置默认" % (cfg_path.name, exc), file=sys.stderr)
            cfg = {}
        for k, v in (cfg.get("urls") or {}).items():
            if k in urls and isinstance(v, str) and v:
                urls[k] = v
            else:
                print("warn: 忽略未知平台 key %r" % k, file=sys.stderr)
        disabled = {k for k in (cfg.get("disabled") or []) if k in urls}
        for k in (cfg.get("disabled") or []):
            if k not in urls:
                print("warn: disabled 里的未知平台 key %r 已忽略" % k, file=sys.stderr)
        page = cfg.get("aggregator_page")
        if isinstance(page, str) and page:
            aggregator_page = page
        return urls, disabled, aggregator_page, cfg_path
    return urls, disabled, aggregator_page, None


def fetch_json(url, method="GET", timeout=20):
    if method == "POST":
        # em 需要 pageNo/pageSize 才返回 100 行；空 body 只回 10 行
        body = b'{"pageNo":1,"pageSize":100}'
        req = urllib.request.Request(url, data=body, headers={**UA, "Content-Type": "application/json"})
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


def fetch_all(urls=None, disabled=None, timeout=20):
    """返回 (platform_lists, status)。

    platform_lists: {platform_key: [rows...]}，失败/禁用/解析为空的平台为空列表；
    status: {platform_key: 'ok' | 'disabled' | 'empty' | 'fail: <原因>'}，
    供调用方与输出明确上报不可用平台（降级链末端不再静默吞错）。
    """
    urls = urls or URLS
    disabled = disabled or set()
    out = {}
    status = {}
    for key in ORDER:
        if key in disabled:
            out[key] = []
            status[key] = "disabled"
            continue
        try:
            obj = fetch_json(urls[key], method="POST" if key == "em" else "GET", timeout=timeout)
            rows = PARSERS[key](obj)
            out[key] = rows
            status[key] = "ok" if rows else "empty"
        except Exception as exc:
            out[key] = []
            status[key] = "fail: %s" % exc
    return out, status


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


def safe_url(url):
    """对 URL 的 path 做百分号编码（urllib 不接受含中文等非 ASCII 的 URL）。"""
    parts = urlsplit(url)
    path = quote(parts.path, safe="/")
    query = quote(parts.query, safe="&=%_+")
    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def check(config_path=None, timeout=20):
    """失效自检：逐平台探测接口（请求 + 解析行数）并探活聚合页。

    返回 True/False；启用平台 FAIL 或解析为空、聚合页不可达均算失效
    （解析为空通常意味着接口结构变了，正是本检查要抓的时效性问题）。
    """
    urls, disabled, aggregator_page, cfg_path = load_sources_config(config_path)
    print("配置来源：%s" % (cfg_path if cfg_path else "内置默认（未找到 %s）" % CONFIG_FILENAME))
    ok_all = True
    for key in ORDER:
        label = PLATFORMS[key][0]
        if key in disabled:
            print("  %-4s %-8s DISABLED（已在配置中禁用）" % (key, label))
            continue
        try:
            obj = fetch_json(urls[key], method="POST" if key == "em" else "GET", timeout=timeout)
            n = len(PARSERS[key](obj))
            if n:
                print("  %-4s %-8s OK      rows=%d" % (key, label, n))
            else:
                ok_all = False
                print("  %-4s %-8s EMPTY   解析为空（疑似结构变动）" % (key, label))
        except Exception as exc:
            ok_all = False
            print("  %-4s %-8s FAIL    %s" % (key, label, exc))
    try:
        req = urllib.request.Request(safe_url(aggregator_page), headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            print("  agg  %-8s OK      HTTP %d" % ("聚合页", resp.status))
    except Exception as exc:
        ok_all = False
        print("  agg  %-8s FAIL    %s" % ("聚合页", exc))
    print("自检结果：%s" % ("通过" if ok_all else "存在失效源，docs 结论可能已过期"))
    return ok_all


def main():
    ap = argparse.ArgumentParser(description="stock-hots 程序化取数")
    ap.add_argument("--json", nargs="?", const="-", default=None, help="输出简要 JSON（- 或省略参数为 stdout；可跟文件路径）")
    ap.add_argument("--top", type=int, default=10, help="综合前十取前 N（默认 10）")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--config", default=None, help="数据源配置文件（默认：脚本上级目录 sources.json，缺省用内置默认）")
    ap.add_argument("--check", action="store_true", help="失效自检：逐平台探测接口 + 探活聚合页，不做综合计算")
    args = ap.parse_args()

    if args.check:
        sys.exit(0 if check(args.config, timeout=args.timeout) else 1)

    urls, disabled, _aggregator_page, cfg_path = load_sources_config(args.config)
    platform_lists, status = fetch_all(urls=urls, disabled=disabled, timeout=args.timeout)
    stocks = build_ranks(platform_lists)
    top = top10(stocks, n=args.top)
    pt = platform_top(platform_lists, stocks)
    ok_platforms = [k for k in ORDER if status[k] == "ok"]

    payload = {
        "source": "wzslinker-8-platform-apis",
        "config": str(cfg_path) if cfg_path else "builtin-defaults",
        "snapshot_time": now_iso(),
        "algorithm": "avg-rank (mean of present platform ranks; more platforms first)",
        "depths": {k: PLATFORMS[k][1] for k in ORDER},
        "platform_status": status,
        "ok_platforms": ok_platforms,
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
        bad = [k for k in ORDER if status[k] != "ok"]
        if bad:
            parts = []
            for k in bad:
                reason = _STATUS_ZH.get(status[k], status[k])
                parts.append("%s（%s）" % (PLATFORMS[k][0], reason))
            print("不可用平台：%s" % "、".join(parts))
        if len(ok_platforms) < 3:
            print("警告：可用平台不足 3 个，综合口径（≥3 平台上榜）无候选；请检查 sources.json 或改走聚合页/直连路径。")


if __name__ == "__main__":
    main()
