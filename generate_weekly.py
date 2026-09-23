#!/usr/bin/env python3
"""周榜编排器：抓 GitHub 官方 weekly trending -> 富结构 -> build_series -> render -> gen_copy。

产物落在 output_weekly/<本周一日期>/（与 output/ 平行，避免日榜 github-trending 的 output_dir=output 把本目录误判为一天）。
已正式接入控制台：columns.json 加 github-weekly 栏目（output_dir=output_weekly）。
落盘的中间文件用 data_weekly_<date>.json，避免与日榜的 data_<date>.json / trending_<date>.json 冲突。

用法:
  python generate_weekly.py [周一日期，默认本周一]
"""
import json
import sys
import os
import datetime
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# 内置 Playwright 的 venv 解释器（render.py 依赖它）；
# 部署到服务器时用系统 python3：RENDER_PY=/usr/bin/python3
VENV_PY = os.environ.get("RENDER_PY", "/Users/lhl/.workbuddy/binaries/python/envs/default/bin/python")

# 复用现有脚本的函数（不重复造轮子，也不改写它们）
import fetch_trending as ft
import generate_daily as gd
import gen_copy as gc
import ai_cn  # 中文富化（LLM 优先，无 key 降级本地模板）


def monday_str():
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    return monday.strftime("%Y-%m-%d")


def main(date=None):
    date = date or monday_str()
    print(f"== 生成 GitHub 周榜 {date} ==")

    # 1) 抓官方周榜（直接调函数，内存拿 repos，不落盘 trending_<date>.json，避免与日榜冲突）
    html = ft.fetch_trending_html(since="weekly")
    if not html:
        print("周榜页面抓取失败，退出")
        return
    repos = ft.parse_articles(html)
    print(f"  解析到 {len(repos)} 个仓库")
    if not repos:
        print("周榜为空，退出")
        return
    repos = ft.compliance_filter(repos)
    repos = repos[:10]
    readmes = ft.enrich(repos)
    print(f"  合规过滤后 {len(repos)} 个，gh 富化完成")

    # 2) 富结构化（复用 generate_daily 的启发式，100% 不改它）
    data = gd.build_from_trending(date, repos, readmes)
    data = ai_cn.enrich_cn(data)  # 中文富化：有 key 走 LLM，无 key 走本地模板
    data_file = ROOT / f"data_weekly_{date}.json"
    data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  富结构 {data_file.name} 就绪")

    # 3) build_series -> html（period=weekly）
    out_dir = ROOT / "output_weekly" / date
    out_dir.mkdir(parents=True, exist_ok=True)
    html_file = out_dir / "github-xhs-series.html"
    subprocess.run([sys.executable, str(ROOT / "build_series.py"),
                    str(data_file), str(html_file), "--period", "weekly"], check=True)

    # 4) render -> png（Playwright，复用系统 Chrome）
    png_dir = out_dir / "png"
    if png_dir.exists():
        import shutil; shutil.rmtree(png_dir)
    png_dir.mkdir(parents=True, exist_ok=True)
    print("渲染 PNG ...")
    subprocess.run([VENV_PY, str(ROOT / "render.py"),
                    str(html_file), str(png_dir)],
                   env={**os.environ, "RENDER_CHROME_CHANNEL": os.environ.get("RENDER_CHROME_CHANNEL", "chrome")},
                   check=True)

    # 5) gen_copy -> copy.json（直接调 make_copy，写指定目录，不乱找 data_*.json）
    copy = gc.make_copy(date, data["repos"], "本周", "每周")
    (out_dir / "copy.json").write_text(
        json.dumps(copy, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  文案 {out_dir / 'copy.json'} 就绪")

    # 6) 索引（独立目录，不影响现有日榜 index.json）
    repos_idx = [{
        "rank": r["rank"], "owner": r["owner"], "repo": r["repo"],
        "lang": r["lang"], "today": r["today"], "total": r["total"], "pct": r["pct"],
    } for r in data["repos"]]
    index = {"date": date, "period": "weekly", "meta": data["cover"], "repos": repos_idx}
    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"完成：{out_dir}")
    print(f"  html : {html_file.exists()}")
    print(f"  pngs : {len(list(png_dir.glob('*.png')))} 张")
    print(f"  copy : {(out_dir / 'copy.json').exists()}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    d = argv[0] if argv and not argv[0].startswith("--") else None
    main(d)
