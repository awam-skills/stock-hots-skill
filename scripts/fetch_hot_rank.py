#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stock-hots 示例取数脚本：多平台热门股票榜单获取。

只封装「已验证」的取数路径：
1. 财联社 API（api3.cls.cn/quote/toplist）——接口 URL 已从 WzSLinker 聚合页源码验证；
2. WzSLinker 聚合页 HTML 抓取——仅作连通性探活；完整榜单为 JS 渲染，
   需浏览器渲染读 DOM（见 docs/01-聚合源-wzslinker.md）。

其余平台直连未经受验证，见 docs/ 各平台文档（02 同花顺 / 03 通达信 /
04 东方财富 / 06 开盘啦 / 07 淘股吧 / 08 雪球 / 09 大智慧）。

仅使用标准库，无第三方依赖。
"""
import json
import sys
import urllib.request
from urllib.parse import quote

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CLS_URL = "https://api3.cls.cn/quote/toplist?app=cailianpress&sv=835&os=android"
WZSLINKER_PAGE = (
    "http://wzslinker.top/companys/" + quote("情绪为王-01八一热榜.html")
    + "?_wv=20261005144523"
)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch_text(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def fetch_cls_toplist():
    """财联社热榜：返回 (ok, data)。接口 URL 已验证；返回结构以当日实际为准。"""
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
    ok_wz, info_wz = probe_wzslinker()
    print("wzslinker_page_ok:", ok_wz, "html_bytes:", info_wz)


if __name__ == "__main__":
    main()
