#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stock-hots 示例取数脚本：多平台热门股票榜单获取。

封装两条取数路径并如实上报状态：
1. 财联社 API（api3.cls.cn/quote/toplist）——2026-10-06 验证可用；
   2026-10-08 复测返回 HTML 而非 JSON（疑似接口要求 sign 参数或已迁移），
   直连视为失效，可用路径见 sources.json urls.cls（WzSLinker 代理）。
2. WzSLinker 聚合页 HTML 抓取——仅作连通性探活；完整榜单为 JS 渲染，
   需浏览器渲染读 DOM（见 docs/01-聚合源-wzslinker.md）。

聚合页 URL 优先读 sources.json 的 aggregator_page，缺省用内置默认。
仅使用标准库，无第三方依赖。
"""
import json
import sys
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CLS_URL = "https://api3.cls.cn/quote/toplist?app=cailianpress&sv=835&os=android"
CONFIG_FILENAME = "sources.json"
DEFAULT_WZSLINKER_PAGE = (
    "http://wzslinker.top/companys/情绪为王-01八一热榜.html"
    + "?_wv=20261005144523"
)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def safe_url(url):
    """对 URL 的 path 做百分号编码（urllib 不接受含中文等非 ASCII 的 URL）。"""
    parts = urlsplit(url)
    path = quote(parts.path, safe="/")
    query = quote(parts.query, safe="&=%_+")
    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def aggregator_page_url():
    """聚合页 URL：优先 sources.json 的 aggregator_page，缺省/读失败用内置默认。"""
    cfg_path = Path(__file__).resolve().parent.parent / CONFIG_FILENAME
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        page = cfg.get("aggregator_page")
        if isinstance(page, str) and page:
            return page
    except Exception:
        pass
    return DEFAULT_WZSLINKER_PAGE


WZSLINKER_PAGE = aggregator_page_url()


def fetch_text(url, timeout=15):
    req = urllib.request.Request(safe_url(url), headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def fetch_cls_toplist():
    """财联社热榜：返回 (ok, data/err)。返回非 JSON 即判定接口失效。"""
    try:
        text = fetch_text(CLS_URL)
        return True, json.loads(text)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def probe_wzslinker():
    """WzSLinker 聚合页连通性探活：仅检查页面可访问；榜单数据为 JS 渲染，需浏览器读 DOM。"""
    try:
        text = fetch_text(WZSLINKER_PAGE)
        return True, len(text)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def main():
    ok_cls, data_cls = fetch_cls_toplist()
    print("cls_api_ok:", ok_cls)
    if ok_cls:
        if isinstance(data_cls, list):
            print("cls_top_items:", len(data_cls))
        else:
            print("cls_top_type:", type(data_cls).__name__)
    else:
        print("cls_api_err:", data_cls, "（直连已失效，可用 sources.json urls.cls 代理路径）")
    ok_wz, info_wz = probe_wzslinker()
    print("wzslinker_page_ok:", ok_wz, "html_bytes:" if ok_wz else "err:", info_wz)


if __name__ == "__main__":
    main()
