#!/usr/bin/env python3
"""抓取当日 GitHub Trending（全语言 daily Top N）+ 合规过滤 + gh 富化。

输出（均在脚本同目录）:
  trending_<date>.json : 抓榜结果，含 owner/repo/lang/lang_color/总星/今日星/描述 + gh 富化的 topics/license/homepage
  readme_<date>.json   : { "owner/repo": "<README 前 4000 字符>" }，供 generate_daily 提取安装片段

用法:
  python fetch_trending.py [date] [--top N]
依赖: 标准库；gh CLI 可选（用于 topics/license/readme 富化，缺失则跳过）
"""
import json
import re
import sys
import subprocess
import base64
import datetime
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 合规词清单与词边界正则统一收敛到 compliance.py（fetch_trending 使用）
from compliance import filter_items


def today_str():
    return datetime.date.today().strftime("%Y-%m-%d")


def fetch_trending_html(since="daily"):
    url = f"https://github.com/trending?since={since}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print("  trending 页面抓取失败:", e)
        return None


def parse_articles(html):
    blocks = re.split(r'<article class="Box-row">', html)[1:]
    repos = []
    for i, b in enumerate(blocks, 1):
        m = re.search(r'<h2[^>]*>\s*<a[^>]*href="/([^"]+)"', b)
        if not m:
            continue
        path = m.group(1).strip("/")
        if path.count("/") != 1:
            continue
        owner, repo = path.split("/")
        dm = re.search(r'<p class="col-9[^"]*">([^<]+)</p>', b)
        desc = dm.group(1).strip() if dm else ""
        lm = re.search(r'itemprop="programmingLanguage">([^<]+)<', b)
        lang = lm.group(1).strip() if lm else ""
        lcm = re.search(r'repo-language-color[^>]*style="background-color:\s*([^;"]+)', b)
        lang_color = lcm.group(1).strip() if lcm else "#9aa7b8"
        # 总星数：stargazers 链接里 </svg> 之后的数字（注意 svg 自身属性里有 height="16" 之类，要跳过）
        sm = re.search(r'/stargazers"[^>]*>.*?</svg>\s*([\d,]+)', b, re.DOTALL)
        total = sm.group(1).strip() if sm else ""
        ym = re.search(r'([\d,]+)\s+stars (?:today|this week)', b)
        today = ym.group(1).strip() if ym else ""
        repos.append({
            "rank": i, "owner": owner, "repo": repo,
            "lang": lang, "lang_color": lang_color,
            "total": total, "today": today, "description": desc,
        })
    return repos


def gh_api(path, jq=None):
    cmd = ["gh", "api", path]
    if jq:
        cmd += ["--jq", jq]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return None


def enrich(repos):
    readmes = {}
    for r in repos:
        full = f'{r["owner"]}/{r["repo"]}'
        info = gh_api(f"repos/{full}")
        if info:
            try:
                d = json.loads(info)
                r["topics"] = d.get("topics") or []
                lic = d.get("license") or {}
                r["license"] = lic.get("spdx_id") if isinstance(lic, dict) else None
                r["homepage"] = d.get("homepage") or ""
                if not r["description"]:
                    r["description"] = d.get("description") or ""
                if not r["lang"] and d.get("language"):
                    r["lang"] = d["language"]
            except Exception:
                pass
        rj = gh_api(f"repos/{full}/readme")
        if rj:
            try:
                b64 = json.loads(rj).get("content")
                if b64:
                    txt = base64.b64decode(b64).decode("utf-8", "ignore")
                    readmes[full] = txt[:4000]
            except Exception:
                pass
    return readmes


# 合规过滤已收敛到 compliance.filter_items（见 compliance.py）


def fallback_search(top):
    """gh api 兜底：取近 2 日新建、按 star 排序的热门仓库（非严格 trending，但可用）。"""
    since = (datetime.date.today() - datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    raw = gh_api(f"search/repositories?q=created:%3E{since}&sort=stars&order=desc&per_page={top}")
    repos = []
    if not raw:
        return repos
    try:
        for i, it in enumerate(json.loads(raw)["items"], 1):
            repos.append({
                "rank": i,
                "owner": it["owner"]["login"],
                "repo": it["name"],
                "lang": it.get("language") or "",
                "lang_color": "#9aa7b8",
                "total": f'{it["stargazers_count"]:,}',
                "today": "",
                "description": it.get("description") or "",
            })
    except Exception as e:
        print("  兜底解析失败:", e)
    return repos


def main(date=None, top=10, since="daily"):
    date = date or today_str()
    print(f"== 抓取 GitHub Trending {date} ({since}) ==")
    html = fetch_trending_html(since)
    if html:
        repos = parse_articles(html)
        print(f"  解析到 {len(repos)} 个仓库")
    else:
        print("  改用 gh api 兜底搜索...")
        repos = fallback_search(top)
        print(f"  兜底得到 {len(repos)} 个仓库")
    if not repos:
        print("抓取彻底失败，退出")
        return
    repos = filter_items(repos, lambda r: f'{r["owner"]}/{r["repo"]} {r["description"]}')
    repos = repos[:top]
    print(f"  合规过滤后 {len(repos)} 个，开始 gh 富化...")
    readmes = enrich(repos)
    (ROOT / f"trending_{date}.json").write_text(
        json.dumps(repos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ROOT / f"readme_{date}.json").write_text(
        json.dumps(readmes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已写出 trending_{date}.json ({len(repos)} 仓库) + readme_{date}.json")
    for r in repos:
        print(f"  #{r['rank']:02d} {r['owner']}/{r['repo']} ★{r['total']} +{r['today']} [{r['lang']}]")


if __name__ == "__main__":
    argv = sys.argv[1:]
    d = argv[0] if argv and not argv[0].startswith("--") else None
    t = 10
    if "--top" in argv:
        try:
            t = int(argv[argv.index("--top") + 1])
        except Exception:
            pass
    since = "daily"
    if "--since" in argv:
        try:
            since = argv[argv.index("--since") + 1]
        except Exception:
            pass
    main(d, t, since)
