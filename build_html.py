# -*- coding: utf-8 -*-
"""生成单文件 HTML 市场情绪日报（全内联，可离线打开）。数据来自 report_data.json。"""
import json

BASE = "G:/Projects/19AI/skills/stock/stock-hots"
data = json.load(open(f"{BASE}/report_data.json", encoding="utf-8"))

dt = data["dragon_tiger"]
th = data["ths_hot"]
ind = data["industry"]
TRADE_DATE = data["trade_date"]

# ---------- 概览 ----------
listed = dt["total_records"]
net_total_wan = sum(s["net_buy_wan"] for s in dt["stocks"])
pos = sum(1 for s in dt["stocks"] if s["net_buy_wan"] > 0)
neg = sum(1 for s in dt["stocks"] if s["net_buy_wan"] < 0)
top_theme = th["themes"][0] if th["themes"] else {"theme": "—", "count": 0}
themes = th["themes"][:15]

# ---------- 行业板块（新浪财经，最新交易日）----------
boards = ind.get("boards", [])
ind_top = boards[:10]                                   # 已按涨跌幅降序
ind_bot = sorted(boards[-10:], key=lambda x: x["chg"])  # 垫底 10（升序，最弱在前）
lead_ind = ind_top[0] if ind_top else {"name": "—", "chg": 0}
lag_ind = ind_bot[0] if ind_bot else {"name": "—", "chg": 0}
ind_total = ind.get("total", len(boards))

# ---------- 龙虎榜 ----------
stocks_sorted = sorted(dt["stocks"], key=lambda x: x["net_buy_wan"], reverse=True)
net_buy_top = stocks_sorted[:15]
net_sell_top = sorted(dt["stocks"], key=lambda x: x["net_buy_wan"])[:8]
detail_buy = stocks_sorted[:20]
detail_sell = net_sell_top

# ---------- 强势股（同花顺，按涨幅降序前20）----------
hot_sorted = sorted(th["hot"], key=lambda x: float(x.get("zhangfu") or 0), reverse=True)
hot_top = hot_sorted[:20]

# ---------- 工具函数 ----------
def fmt_amt(wan):
    if wan is None:
        return "—"
    if wan >= 10000 or wan <= -10000:
        return f"{wan/10000:+.2f}亿".replace("+-", "-")
    return f"{wan:+,.0f}万".replace("+-", "-")

def fmt_chg(x):
    if x is None:
        return "—"
    return f"{x:+.2f}%"

def color_up(x):
    return "up" if x >= 0 else "down"

def fmt_yi(y):
    if not y:
        return "—"
    return f"{y:.1f}亿"

# ---------- SVG 条形图 ----------
def hbar_chart(items, value_key, label_key, bar_color=None, unit="amt"):
    if not items:
        return ""
    vals = [abs(it[value_key]) for it in items]
    mx = max(vals) if vals else 1
    mx = mx or 1
    row_h = 22
    label_w = 130
    bar_max = 460
    h = row_h * len(items) + 12
    svg = [f'<svg viewBox="0 0 {label_w+bar_max+130} {h}" width="100%" preserveAspectRatio="xMinYMin meet" style="font-family:inherit">']
    for i, it in enumerate(items):
        y = 6 + i * row_h
        v = it[value_key]
        av = abs(v)
        w = max(bar_max * (av / mx), 2)
        c = bar_color or ("#f6465d" if v >= 0 else "#0ecb81")
        name = str(it[label_key])
        if len(name) > 9:
            name = name[:9] + "…"
        svg.append(f'<text x="0" y="{y+14}" fill="#c9d4e3" font-size="13">{name}</text>')
        svg.append(f'<rect x="{label_w}" y="{y+3}" width="{w:.1f}" height="15" rx="2" fill="{c}" opacity="0.92"/>')
        valtxt = (fmt_amt(v) if unit == "amt" else fmt_chg(v)) if unit in ("amt", "pct") else str(v)
        svg.append(f'<text x="{label_w+w+8:.1f}" y="{y+15}" fill="{c}" font-size="12.5" font-weight="600">{valtxt}</text>')
    svg.append('</svg>')
    return "\n".join(svg)

# 题材热度（计数，橙）
themes_for_chart = [{"name": t["theme"], "v": t["count"]} for t in themes]
theme_svg = hbar_chart(themes_for_chart, "v", "name", bar_color="#f0883e", unit="cnt")

# 行业领涨（红）/ 领跌（绿）
ind_top_svg = hbar_chart([{"name": x["name"], "v": x["chg"]} for x in ind_top], "v", "name", bar_color="#f6465d", unit="pct")
ind_bot_svg = hbar_chart([{"name": x["name"], "v": x["chg"]} for x in ind_bot], "v", "name", bar_color="#0ecb81", unit="pct")

# 龙虎榜净买入 TOP15 / 净卖出 TOP8
lhb_buy_svg = hbar_chart([{"name": s["name"], "v": s["net_buy_wan"]} for s in net_buy_top], "v", "name", bar_color="#f6465d", unit="amt")
lhb_sell_svg = hbar_chart([{"name": s["name"], "v": s["net_buy_wan"]} for s in net_sell_top], "v", "name", bar_color="#0ecb81", unit="amt")

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# 龙虎榜明细表
def lhb_rows(rows):
    out = []
    for s in rows:
        cls = "up" if s["net_buy_wan"] >= 0 else "down"
        out.append(f"""<tr>
<td class="mono">{esc(s['code'])}</td>
<td>{esc(s['name'])}</td>
<td class="{color_up(s['change_pct'])}">{fmt_chg(s['change_pct'])}</td>
<td class="{cls}">{fmt_amt(s['net_buy_wan'])}</td>
<td class="reason">{esc(s['reason'])}</td>
<td>{s['turnover_pct']:.2f}%</td></tr>""")
    return "\n".join(out)

# 强势股表
def hot_rows(rows):
    out = []
    for s in rows:
        zf = float(s.get("zhangfu") or 0)
        hs = float(s.get("huanshou") or 0)
        out.append(f"""<tr>
<td class="mono">{esc(s['code'])}</td>
<td>{esc(s['name'])}</td>
<td class="{color_up(zf)}">{fmt_chg(zf)}</td>
<td>{hs:.2f}%</td>
<td class="reason">{esc(s.get('reason',''))}</td></tr>""")
    return "\n".join(out)

# 行业明细表（领涨 TOP10 + 领跌 TOP10 合并展示）
def ind_rows(rows):
    out = []
    for x in rows:
        cls = "up" if x["chg"] >= 0 else "down"
        out.append(f"""<tr>
<td>{esc(x['name'])}</td>
<td class="{cls}">{fmt_chg(x['chg'])}</td>
<td style="text-align:right">{x.get('stocks','—')}</td>
<td>{esc(x.get('leader','—'))}</td>
<td class="{color_up(x.get('leader_chg',0))}">{fmt_chg(x.get('leader_chg',0))}</td>
<td style="text-align:right">{fmt_yi(x.get('amount_yi',0))}</td></tr>""")
    return "\n".join(out)

net_total_yi = net_total_wan / 10000
industry_note = (f"数据来源：新浪财经行业板块（Sina sinaindustry，共 {ind_total} 个行业，"
                 f"按涨跌幅排序；领涨股/成分股数为该板块当日数据）。"
                 f"注：东方财富行业板块接口（push2）在本运行环境被网络策略拦截，故行业部分改用新浪财经真实数据。")

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A股龙虎榜情绪日报 · {TRADE_DATE}</title>
<style>
  :root {{
    --bg:#0a0e14; --panel:#121821; --panel2:#0f141c; --border:#1e2734;
    --text:#e6edf3; --muted:#8b97a7; --dim:#5b6675;
    --up:#f6465d; --down:#0ecb81; --accent:#f0883e; --gold:#e3b341;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:
    radial-gradient(1200px 600px at 80% -10%, #14202e 0%, transparent 60%),
    radial-gradient(900px 500px at -10% 10%, #16121f 0%, transparent 55%),
    var(--bg);
    color:var(--text); font-family:-apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,Roboto,Helvetica,Arial,sans-serif;
    font-size:14px; line-height:1.5; -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:1180px; margin:0 auto; padding:22px 18px 60px; }}
  header.hero {{ border:1px solid var(--border); border-radius:14px; padding:20px 22px;
    background:linear-gradient(135deg,#10161f 0%,#0c1119 100%); position:relative; overflow:hidden; }}
  header.hero::before {{ content:""; position:absolute; right:-40px; top:-40px; width:220px; height:220px;
    background:radial-gradient(circle, rgba(246,70,93,.18), transparent 70%); }}
  .kicker {{ color:var(--accent); font-size:12px; letter-spacing:2px; font-weight:600; }}
  h1 {{ margin:6px 0 4px; font-size:27px; letter-spacing:1px; }}
  .sub {{ color:var(--muted); font-size:13px; }}
  .datepill {{ display:inline-block; margin-top:10px; padding:4px 12px; border:1px solid var(--border);
    border-radius:20px; color:var(--gold); font-size:13px; font-weight:600; }}
  .ov {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:16px 0 6px; }}
  .card {{ background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:14px 16px; }}
  .card .lab {{ color:var(--muted); font-size:12px; }}
  .card .val {{ font-size:25px; font-weight:700; margin-top:6px; letter-spacing:.5px; }}
  .card .note {{ color:var(--dim); font-size:11.5px; margin-top:3px; }}
  .val.up {{ color:var(--up); }} .val.down {{ color:var(--down); }} .val.gold {{ color:var(--gold); }}
  section {{ margin-top:22px; border:1px solid var(--border); border-radius:14px; background:var(--panel2); overflow:hidden; }}
  .shead {{ display:flex; align-items:baseline; gap:12px; padding:13px 18px; border-bottom:1px solid var(--border);
    background:linear-gradient(90deg,#141b25,#0f141c); }}
  .shead h2 {{ margin:0; font-size:16px; }}
  .shead .note {{ color:var(--dim); font-size:12px; }}
  .sbody {{ padding:14px 18px 18px; }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
  .subh {{ font-size:13px; color:var(--muted); margin:0 0 6px; font-weight:600; }}
  .subh .tag {{ color:var(--up); }} .subh .tagd {{ color:var(--down); }}
  table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
  th,td {{ text-align:left; padding:6px 8px; border-bottom:1px solid #18202b; }}
  th {{ color:var(--muted); font-weight:600; font-size:11.5px; }}
  td.mono {{ font-family:"SFMono-Regular",Consolas,monospace; color:var(--dim); }}
  td.reason {{ color:var(--text); font-size:11.5px; }}
  .up {{ color:var(--up); }} .down {{ color:var(--down); }}
  tr:hover td {{ background:#10161f; }}
  .legend {{ font-size:11.5px; color:var(--dim); margin-top:6px; }}
  .legend .up {{ color:var(--up); }} .legend .down {{ color:var(--down); }}
  footer {{ margin-top:26px; padding:16px 18px; border:1px solid var(--border); border-radius:12px;
    background:var(--panel); color:var(--muted); font-size:12px; }}
  footer b {{ color:var(--text); }}
  .warn {{ color:var(--gold); margin-top:8px; }}
  @media (max-width:760px) {{ .ov{{grid-template-columns:repeat(2,1fr);}} .grid2{{grid-template-columns:1fr;}} }}
</style>
</head>
<body>
<div class="wrap">

<header class="hero">
  <div class="kicker">A-SHARE MARKET SENTIMENT · 收盘复盘</div>
  <h1>A股龙虎榜情绪日报</h1>
  <div class="sub">龙虎榜资金动向 · 题材热点归因 · 行业轮动全景 —— 由「A股全栈数据」skill 抓取</div>
  <div class="datepill">报告交易日：{TRADE_DATE}（最新交易日）</div>
</header>

<!-- 概览 -->
<div class="ov">
  <div class="card">
    <div class="lab">龙虎榜上榜</div>
    <div class="val gold">{listed}<span style="font-size:14px;color:var(--muted)"> 家</span></div>
    <div class="note">净买入为正 {pos} / 为负 {neg}</div>
  </div>
  <div class="card">
    <div class="lab">净买入合计</div>
    <div class="val up">{net_total_yi:+.2f}亿</div>
    <div class="note">全部上榜个股净买入求和</div>
  </div>
  <div class="card">
    <div class="lab">最热题材</div>
    <div class="val" style="color:var(--accent)">{esc(top_theme['theme'])}</div>
    <div class="note">{top_theme['count']} 只强势股共振</div>
  </div>
  <div class="card">
    <div class="lab">领涨 / 领跌行业</div>
    <div class="val up">{esc(lead_ind['name'])} {fmt_chg(lead_ind['chg'])}</div>
    <div class="note">领跌 {esc(lag_ind['name'])} {fmt_chg(lag_ind['chg'])}</div>
  </div>
</div>

<!-- 题材热度 -->
<section>
  <div class="shead"><h2>题材热度榜</h2><span class="note">同花顺强势股 reason 按「+」拆分词频统计 · TOP 15</span></div>
  <div class="sbody">
    <p class="subh">出现次数越多 = 当日题材共振越强</p>
    {theme_svg}
  </div>
</section>

<!-- 行业轮动 -->
<section>
  <div class="shead"><h2>行业轮动</h2><span class="note">新浪财经行业板块 · 共 {ind_total} 个行业 · 涨红跌绿</span></div>
  <div class="sbody">
    <div class="grid2">
      <div>
        <p class="subh"><span class="tag">涨幅榜 TOP 10</span> · 领涨</p>
        {ind_top_svg}
      </div>
      <div>
        <p class="subh"><span class="tagd">涨幅垫底 TOP 10</span> · 最弱</p>
        {ind_bot_svg}
      </div>
    </div>
    <p class="subh" style="margin-top:18px">领涨行业 TOP 10 明细</p>
    <div style="overflow-x:auto">
    <table>
      <thead><tr><th>行业</th><th>涨跌幅</th><th style="text-align:right">成分股</th><th>领涨股</th><th>领涨股涨跌幅</th><th style="text-align:right">成交额</th></tr></thead>
      <tbody>
      {ind_rows(ind_top)}
      </tbody>
    </table>
    </div>
    <p class="subh" style="margin-top:16px">领跌行业 TOP 10 明细</p>
    <div style="overflow-x:auto">
    <table>
      <thead><tr><th>行业</th><th>涨跌幅</th><th style="text-align:right">成分股</th><th>领涨股</th><th>领涨股涨跌幅</th><th style="text-align:right">成交额</th></tr></thead>
      <tbody>
      {ind_rows(ind_bot)}
      </tbody>
    </table>
    </div>
    <div class="legend"><span class="up">红 = 上涨</span> &nbsp; <span class="down">绿 = 下跌</span> &nbsp;|&nbsp; {industry_note}</div>
  </div>
</section>

<!-- 龙虎榜核心 -->
<section>
  <div class="shead"><h2>龙虎榜核心</h2><span class="note">全市场上榜 · 按净买入降序 · 正红负绿</span></div>
  <div class="sbody">
    <div class="grid2">
      <div>
        <p class="subh"><span class="tag">净买入 TOP 15</span> 排名</p>
        {lhb_buy_svg}
      </div>
      <div>
        <p class="subh"><span class="tagd">净卖出 TOP 8</span> 资金出逃</p>
        {lhb_sell_svg}
      </div>
    </div>

    <p class="subh" style="margin-top:18px">净买入 TOP 20 明细</p>
    <div style="overflow-x:auto">
    <table>
      <thead><tr><th>代码</th><th>名称</th><th>涨跌幅</th><th>净买入</th><th>上榜原因</th><th>换手</th></tr></thead>
      <tbody>
      {lhb_rows(detail_buy)}
      </tbody>
    </table>
    </div>

    <p class="subh" style="margin-top:16px">净卖出 TOP 8（资金出逃）</p>
    <div style="overflow-x:auto">
    <table>
      <thead><tr><th>代码</th><th>名称</th><th>涨跌幅</th><th>净买入</th><th>上榜原因</th><th>换手</th></tr></thead>
      <tbody>
      {lhb_rows(detail_sell)}
      </tbody>
    </table>
    </div>
  </div>
</section>

<!-- 强势股题材归因 -->
<section>
  <div class="shead"><h2>强势股题材归因</h2><span class="note">同花顺当日强势股 {th['count']} 只 · 按涨幅降序取前 20</span></div>
  <div class="sbody">
    <div style="overflow-x:auto">
    <table>
      <thead><tr><th>代码</th><th>名称</th><th>涨幅</th><th>换手</th><th>题材归因</th></tr></thead>
      <tbody>
      {hot_rows(hot_top)}
      </tbody>
    </table>
    </div>
  </div>
</section>

<footer>
  <div><b>数据来源：</b>东方财富全市场龙虎榜（RPT_DAILYBILLBOARD_DETAILSNEW）· 同花顺当日强势股题材热点（zx.10jqka.com.cn）· 行业板块（新浪财经 Sina sinaindustry，因东方财富 push2 板块接口在本环境被网络策略拦截而改用）</div>
  <div style="margin-top:6px"><b>交易日期：</b>{TRADE_DATE}（最新交易日） &nbsp;|&nbsp; 龙虎榜上榜 {listed} 家 &nbsp;|&nbsp; 题材词频源自同花顺强势股 {th['count']} 只 &nbsp;|&nbsp; 行业板块 {ind_total} 个</div>
  <div class="warn">⚠ 本报告由 AI 基于「A股全栈数据」skill 自动抓取生成，仅供研究参考，不构成任何投资建议。市场有风险，入市需谨慎。</div>
</footer>

</div>
</body>
</html>"""

out_path = f"{BASE}/stock_hots_daily_{TRADE_DATE}.html"
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)

print("行业 TOP10:", [(x["name"], x["chg"]) for x in ind_top])
print("行业 BOTTOM10:", [(x["name"], x["chg"]) for x in ind_bot])
print("输出:", out_path, "字节:", len(html))
