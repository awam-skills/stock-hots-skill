# -*- coding: utf-8 -*-
"""
抓取「龙虎榜 + 题材热点 + 行业轮动」市场情绪日报真实数据（最新交易日）
数据源:
  龙虎榜     - 东方财富 datacenter-web (RPT_DAILYBILLBOARD_DETAILSNEW)
  题材热点   - 同花顺当日强势股 (zx.10jqka.com.cn getharden)
  行业板块   - 新浪财经行业板块 (money.finance.sina.com.cn newSinaHy.php, 最新交易日)
仅依赖标准库 urllib + json（无需 requests/pandas）。
"""
import urllib.request
import urllib.parse
import json
import time
import random
import re
import datetime
from collections import Counter

OUT_PATH = "G:/Projects/19AI/skills/stock/stock-hots/report_data.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36")

# 东财防封：串行限流 + 会话复用
_em_last_call = [0.0]
EM_MIN_INTERVAL = 1.0
opener = urllib.request.build_opener(urllib.request.HTTPHandler(debuglevel=0))


def em_get(url, params=None, referer=None, timeout=15):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    last_err = None
    for attempt in range(3):
        req = urllib.request.Request(url)
        req.add_header("User-Agent", UA)
        if referer:
            req.add_header("Referer", referer)
        try:
            with opener.open(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8")
            _em_last_call[0] = time.time()
            return raw
        except Exception as e:
            last_err = e
            time.sleep(1.5 + random.uniform(0.2, 0.8))
    _em_last_call[0] = time.time()
    raise last_err


def eastmoney_datacenter(report_name, columns="ALL", filter_str="", page_size=500,
                         sort_columns="", sort_types="-1"):
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": report_name,
        "columns": columns,
        "filter": filter_str,
        "pageNumber": "1",
        "pageSize": str(page_size),
        "sortColumns": sort_columns,
        "sortTypes": sort_types,
        "source": "WEB",
        "client": "WEB",
    }
    raw = em_get(url, params=params, referer="https://data.eastmoney.com/")
    d = json.loads(raw)
    if d.get("result") and d["result"].get("data"):
        return d["result"]["data"]
    return []


def find_latest_trading_day():
    """从今天往前找最近一个有龙虎榜数据的交易日。"""
    today = datetime.date.today()
    for back in range(0, 15):
        d = today - datetime.timedelta(days=back)
        if d.weekday() >= 5:      # 跳过周六周日
            continue
        rows = eastmoney_datacenter(
            "RPT_DAILYBILLBOARD_DETAILSNEW",
            filter_str=f"(TRADE_DATE>='{d.isoformat()}')(TRADE_DATE<='{d.isoformat()}')",
            page_size=10,
        )
        if rows:
            return d.isoformat()
    return today.isoformat()


def fetch_dragon_tiger(trade_date):
    print("[1/3] 抓取全市场龙虎榜 ...", flush=True)
    rows = eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAILSNEW",
        filter_str=f"(TRADE_DATE>='{trade_date}')(TRADE_DATE<='{trade_date}')",
        page_size=500,
        sort_columns="BILLBOARD_NET_AMT",
        sort_types="-1",
    )
    if not rows:
        return {"date": trade_date, "total_records": 0, "stocks": []}
    stocks = []
    for row in rows:
        net_buy = (row.get("BILLBOARD_NET_AMT") or 0) / 10000.0  # 万元
        stocks.append({
            "code": row.get("SECURITY_CODE", ""),
            "name": row.get("SECURITY_NAME_ABBR", ""),
            "reason": row.get("EXPLANATION", ""),
            "close": row.get("CLOSE_PRICE") or 0,
            "change_pct": round(float(row.get("CHANGE_RATE") or 0), 2),
            "net_buy_wan": round(net_buy, 1),
            "buy_wan": round((row.get("BILLBOARD_BUY_AMT") or 0) / 10000.0, 1),
            "sell_wan": round((row.get("BILLBOARD_SELL_AMT") or 0) / 10000.0, 1),
            "turnover_pct": round(float(row.get("TURNOVERRATE") or 0), 2),
        })
    stocks.sort(key=lambda x: x["net_buy_wan"], reverse=True)
    return {"date": trade_date, "total_records": len(stocks), "stocks": stocks}


def fetch_ths_hot(trade_date):
    print("[2/3] 抓取同花顺当日强势股题材归因 ...", flush=True)
    url = (f"https://zx.10jqka.com.cn/event/api/getharden/"
           f"date/{trade_date}/orderby/date/orderway/desc/charset/GBK/")
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
        try:
            text = raw.decode("gbk")
        except Exception:
            text = raw.decode("utf-8", errors="ignore")
        d = json.loads(text)
    except Exception as e:
        print(f"  同花顺热点抓取失败: {e}", flush=True)
        return {"date": trade_date, "count": 0, "hot": [], "themes": []}
    if d.get("errocode", 0) != 0:
        print(f"  同花顺错误: {d.get('errormsg')}", flush=True)
        return {"date": trade_date, "count": 0, "hot": [], "themes": []}
    data = d.get("data") or []
    hot = []
    all_tags = []
    for item in data:
        reason = item.get("reason", "") or ""
        tags = [t.strip() for t in str(reason).split("+") if t.strip()]
        all_tags.extend(tags)
        hot.append({
            "code": item.get("code", ""),
            "name": item.get("name", ""),
            "reason": reason,
            "close": item.get("close") or 0,
            "zhangfu": item.get("zhangfu") or 0,
            "zhangdie": item.get("zhangdie") or 0,
            "huanshou": item.get("huanshou") or 0,
            "chengjiaoe": item.get("chengjiaoe") or 0,
            "tags": tags,
        })
    cnt = Counter(all_tags)
    themes = [{"theme": t, "count": n} for t, n in cnt.most_common(30)]
    return {"date": trade_date, "count": len(hot), "hot": hot, "themes": themes}


def fetch_industry():
    """新浪财经行业板块（最新交易日）。返回涨跌幅排名、领涨/领跌、领涨股。"""
    print("[3/3] 抓取新浪财经全市场行业板块 ...", flush=True)
    url = "https://money.finance.sina.com.cn/q/view/newSinaHy.php"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    req.add_header("Referer", "https://finance.sina.com.cn/")
    boards = []
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("gbk", "ignore")
        i = html.find("S_Finance_bankuai_sinaindustry")
        if i < 0:
            return {"source": "新浪财经", "total": 0, "boards": []}
        seg = html[i:]
        ob = seg.find("{", seg.find("="))
        cb = seg.rfind("}")
        if ob < 0 or cb < 0:
            return {"source": "新浪财经", "total": 0, "boards": []}
        body = seg[ob + 1:cb]
        for _k, v in re.findall(r'"([^"]+)":"([^"]*)"', body):
            f = v.split(",")
            if len(f) < 11:
                continue
            try:
                boards.append({
                    "name": f[1],
                    "chg": float(f[5]),          # 涨跌幅 %
                    "stocks": int(float(f[2])),  # 成分股数量
                    "leader": f[12] if len(f) > 12 else "",   # 领涨股名称
                    "leader_chg": float(f[9]) if len(f) > 9 else 0,  # 领涨股涨跌幅
                    "amount_yi": float(f[7]) / 1e8 if len(f) > 7 else 0,  # 成交额(元->亿)
                })
            except (ValueError, IndexError):
                continue
    except Exception as e:
        print(f"  新浪行业板块抓取失败: {e}", flush=True)
        return {"source": "新浪财经", "total": 0, "boards": []}
    boards.sort(key=lambda x: x["chg"], reverse=True)
    return {"source": "新浪财经", "total": len(boards), "boards": boards}


def main():
    trade_date = find_latest_trading_day()
    print(f"最新交易日 = {trade_date}", flush=True)
    result = {}
    result["trade_date"] = trade_date
    result["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        result["dragon_tiger"] = fetch_dragon_tiger(trade_date)
    except Exception as e:
        print(f"龙虎榜失败: {e}", flush=True)
        result["dragon_tiger"] = {"date": trade_date, "total_records": 0, "stocks": []}
    try:
        result["ths_hot"] = fetch_ths_hot(trade_date)
    except Exception as e:
        print(f"同花顺热点失败: {e}", flush=True)
        result["ths_hot"] = {"date": trade_date, "count": 0, "hot": [], "themes": []}
    try:
        result["industry"] = fetch_industry()
    except Exception as e:
        print(f"行业板块失败: {e}", flush=True)
        result["industry"] = {"source": "新浪财经", "total": 0, "boards": []}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    dt = result["dragon_tiger"]
    th = result["ths_hot"]
    ind = result["industry"]
    net_total_wan = sum(s["net_buy_wan"] for s in dt["stocks"])
    print("\n=== 抓取完成 ===", flush=True)
    print(f"龙虎榜: {dt['total_records']} 条, 净买入合计 {net_total_wan/10000:.2f}亿", flush=True)
    print(f"同花顺强势股: {th['count']} 只, TOP题材: {th['themes'][:5] if th['themes'] else '无'}", flush=True)
    print(f"行业板块: {ind['total']} 个 (来源 {ind['source']}), 领涨: "
          f"{ind['boards'][0]['name']} {ind['boards'][0]['chg']:+.2f}%" if ind['boards'] else "行业板块: 无", flush=True)
    print(f"已保存: {OUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
