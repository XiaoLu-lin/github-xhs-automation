#!/usr/bin/env python3
"""公共合规过滤：供 fetch_trending.py 使用（词边界正则，避免子串误杀正常仓库）。

用法:
  from compliance import filter_items
  repos = filter_items(repos, lambda r: f'{r["owner"]}/{r["repo"]} {r["description"]}')
  news  = filter_items(news, lambda n: f'{n["title"]} {n["summary"]}')
"""
import re

# 合规过滤词：翻墙 / 科学上网 / 代理类工具，避免出现在科技藏宝图内容中。
# 注意：所有来源都 import 本模块，扩展词只需改这一处。
SENSITIVE = [
    "翻墙", "科学上网", "fanqiang", "fuckgfw", "vpn", "proxy", "trojan",
    "ssr", "v2ray", "shadowsocks", "shadowsock", "bannedbook", "自由门",
    "无界", "lantern", "psiphon", "赛风", "突破封锁", "gfw", "circumvent",
    "anti-censorship", "censorship", "zapret",
]

# 词边界匹配：避免 "ssr" 误中 classroom、"proxy" 误中等子串情形。
# 仅当敏感词前后不是字母/数字时才命中（即作为独立词/短语出现）。
_SENSITIVE_PATTERNS = [
    re.compile(r"(?<![a-z0-9])" + re.escape(s.strip()) + r"(?![a-z0-9])", re.IGNORECASE)
    for s in SENSITIVE
]


def hit_word(text):
    """返回命中的敏感词（去空白），未命中返回 None。"""
    t = (text or "").lower()
    for s, p in zip(SENSITIVE, _SENSITIVE_PATTERNS):
        if p.search(t):
            return s
    return None


def filter_items(items, key):
    """按 key(it) 文本做合规过滤，命中则跳过并打印。返回过滤后列表。"""
    out = []
    for it in items:
        w = hit_word(key(it))
        if w:
            label = str(key(it))[:60]
            print(f"  合规过滤跳过: {label} (命中: {w.strip()})")
            continue
        out.append(it)
    return out
