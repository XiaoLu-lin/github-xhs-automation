#!/usr/bin/env python3
"""每日编排器：抓榜 -> 生成富结构 data_<date>.json -> build_series -> render(PNG) -> gen_copy。

落盘位置由 columns.json 决定：github-trending 的 output_dir="output"，
所以产物落在 <ROOT>/output/<date>/（github-xhs-series.html + png/ + copy.json），
控制台（server.py）启动后自动就能读到。

用法:
  python generate_daily.py [date] [--col github-trending]

行为:
  - 若 data_<date>.json 已存在（手写/精修版），直接复用，不再自动生成
  - 否则从 trending_<date>.json + readme_<date>.json 启发式生成富结构
  - 若 trending 文件缺失，会自动先调 fetch_trending.py
  - render 使用内置 Playwright 的 venv 解释器（stdio 脚本用当前解释器即可）
"""
import json
import re
import sys
import os
import subprocess
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# 内置 Playwright 的 venv 解释器（render.py 依赖它）；
# 部署到服务器时用系统 python3：RENDER_PY=/usr/bin/python3（服务器系统 python3 已装 playwright 包）
VENV_PY = os.environ.get("RENDER_PY", "/Users/lhl/.workbuddy/binaries/python/envs/default/bin/python")
# 中文富化（LLM 优先，无 key 降级本地模板）
import ai_cn


def today_str():
    return datetime.date.today().strftime("%Y-%m-%d")


def load_columns():
    return json.loads((ROOT / "columns.json").read_text(encoding="utf-8"))


def col_output_dir(col):
    return ROOT / col["output_dir"]


def write_run_log(date, repos, status, error=""):
    """记录最近一次生成运行，供控制台「自动化」页读取。"""
    log = {
        "last_run": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "date": date, "repos": repos, "status": status, "error": error,
    }
    (ROOT / "run_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def to_int(s):
    if not s:
        return 0
    return int(re.sub(r"[^\d]", "", str(s)) or 0)


def extract_code(readme, full):
    """从 README 提取安装/使用片段；没有就回退到 git clone。"""
    if not readme:
        return [[["cm", "# 直接 clone 拿走"]],
                [["", f"git clone https://github.com/{full}.git"]]]
    fences = re.findall(r"```(\w*)\n(.*?)```", readme, re.DOTALL)
    kw = ["curl ", "pip install", "npm i", "npm install", "docker run",
          "go install", "cargo install", "npx ", "brew install", "git clone",
          "yarn add", "pnpm add"]
    for _, body in fences:
        if any(k in body.lower() for k in kw):
            lines = [l for l in body.strip().splitlines() if l.strip()][:6]
            if lines:
                return [[["", l]] for l in lines]
    for _, body in fences:
        if body.strip():
            lines = [l for l in body.strip().splitlines() if l.strip()][:6]
            if lines:
                return [[["", l]] for l in lines]
    return [[["cm", "# 直接 clone 拿走"]],
            [["", f"git clone https://github.com/{full}.git"]]]


def trunc(s, n=36):
    s = s.strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    if s[n] != " " and " " in cut:
        cut = cut[:cut.rfind(" ")]
    return cut.rstrip(".。 ")


def build_from_trending(date, trending, readmes):
    """启发式把抓榜数据补成 v2 富结构 data_<date>.json。"""
    repos = []
    total_today_sum = 0
    langs = set()
    for t in trending:
        owner, repo = t["owner"], t["repo"]
        full = f"{owner}/{repo}"
        desc = (t.get("description") or "").strip()
        lang = t.get("lang") or "Other"
        lang_color = t.get("lang_color") or "#9aa7b8"
        total = t.get("total") or "0"
        today = t.get("today") or "0"
        total_i, today_i = to_int(total), to_int(today)
        total_today_sum += today_i
        langs.add(lang)
        lic = t.get("license") or "开源"
        lic_short = lic if lic not in (None, "") else "开源"

        tag_full = trunc(desc or repo)
        # 高亮词：仓库名若出现在标语里才高亮，否则不高亮（避免高亮 a/the 等停用词）
        tag_hl = repo if repo.lower() in tag_full.lower() else ""

        chips = [c for c in (t.get("topics") or []) if c][:6]
        if not chips:
            chips = [lang, "开源"]

        code = extract_code(readmes.get(full, ""), full)

        stats = [
            {"v": lang, "k": "语言"},
            {"v": total, "k": "总星"},
            {"v": f"+{today}" if today else "—", "k": "今日新增"},
            {"v": lic_short, "k": "协议"},
        ]
        pct = round(today_i / total_i * 100) if total_i else 0
        pct = min(100, pct)

        repos.append({
            "rank": t["rank"], "owner": owner, "repo": repo,
            "author_note": f"{lic_short} 开源",
            "lang": lang, "lang_color": lang_color,
            "tagline_full": tag_full, "tagline_hl": tag_hl,
            "problem": desc or f"{full} 是一个开源项目。",
            # desc：完整未截断的真实描述（英文或中文），作为小红书正文的主内容源；
            # 中文富化层(ai_cn)在无 LLM key 时会原样保留，不再用模板覆盖。
            "desc": desc,
            "stats": stats, "chips": chips, "code": code,
            "code_caption": f"{lic_short} 开源 · 详见项目 README",
            "today": f"+{today}" if today else "—",
            "total": total, "pct": pct,
            "rank_no": f"#{t['rank']}",
        })

    highlights = [[r["repo"], r["lang"]] for r in repos[:3]]
    cover = {
        "date": date,
        "total_today": f"+{total_today_sum:,}" if total_today_sum else "—",
        "count": len(repos),
        "langs": len(langs),
        "highlights": highlights,
    }
    follow = {
        "handle": "科技藏宝图",
        "slogan": ["每天 1 分钟，", "挖到值得收藏的技术宝藏"],
        "tags": ["#GitHub热点", "#开源项目", "#技术分享", "#程序员", "#每日更新"],
        "sign": "科技藏宝图 · 用真实数据，带你读懂今天的 GitHub",
    }
    return {"cover": cover, "repos": repos, "follow": follow}


def main(date=None, col_id="github-trending"):
    date = date or today_str()
    cols = load_columns()
    col = next((c for c in cols["columns"] if c["id"] == col_id), None)
    if not col:
        print("栏目不存在:", col_id)
        return
    out_dir = col_output_dir(col) / date
    data_file = ROOT / f"data_{date}.json"

    # 1) 准备 data_<date>.json
    if data_file.exists():
        print(f"已存在精修数据 {data_file.name}，直接使用（不覆盖）")
    else:
        trend_file = ROOT / f"trending_{date}.json"
        readme_file = ROOT / f"readme_{date}.json"
        if not trend_file.exists():
            print("未找到 trending json，先抓取...")
            subprocess.run([sys.executable, str(ROOT / "fetch_trending.py"), date], check=False)
        trending = json.loads(trend_file.read_text(encoding="utf-8")) if trend_file.exists() else []
        readmes = json.loads(readme_file.read_text(encoding="utf-8")) if readme_file.exists() else {}
        if not trending:
            print("无 trending 数据，退出")
            return
        data = build_from_trending(date, trending, readmes)
        data = ai_cn.enrich_cn(data)  # 自动生成的中文富化（精修版 data 已存在则跳过此分支）
        data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已生成富结构 {data_file.name}（{len(trending)} 仓库）")

    # 2) build_series -> html
    html_file = out_dir / "github-xhs-series.html"
    print("构建 HTML ...")
    subprocess.run([sys.executable, str(ROOT / "build_series.py"),
                    str(data_file), str(html_file)], check=True)

    # 3) render -> png（Playwright）
    png_dir = out_dir / "png"
    print("渲染 PNG ...")
    subprocess.run([VENV_PY, str(ROOT / "render.py"),
                    str(html_file), str(png_dir)],
                   env={**os.environ, "RENDER_CHROME_CHANNEL": os.environ.get("RENDER_CHROME_CHANNEL", "chrome")},
                   check=True)

    # 4) gen_copy -> copy.json
    print("生成文案 ...")
    subprocess.run([sys.executable, str(ROOT / "gen_copy.py"),
                    date, str(out_dir)], check=True)

    # 5) 写索引 + 运行日志（供控制台 总览 / 数据复盘 / 自动化 读取）
    data = json.loads(data_file.read_text(encoding="utf-8"))
    repos_idx = [{
        "rank": r["rank"], "owner": r["owner"], "repo": r["repo"],
        "lang": r["lang"], "today": r["today"], "total": r["total"], "pct": r["pct"],
    } for r in data["repos"]]
    index = {"date": date, "meta": data["cover"], "repos": repos_idx}
    (out_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    write_run_log(date, len(data["repos"]), "ok")

    # 6) 清理过期发布记录（保留最近 14 天，释放本地磁盘；失败不影响本次生成）
    try:
        import prune_old
        cutoff, removed, freed = prune_old.prune(retention_days=14)
        if removed:
            print(f"已清理 {len(removed)} 个过期发布记录（保留线 {cutoff}），释放约 {freed/1024/1024:.1f} MB")
    except Exception as e:
        print("清理过期发布记录跳过（不影响本次生成）:", e)

    print(f"完成：{out_dir}")
    print(f"  html : {html_file.exists()}")
    print(f"  pngs : {len(list(png_dir.glob('*.png')))} 张")
    print(f"  copy : {(out_dir / 'copy.json').exists()}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    d = argv[0] if argv and not argv[0].startswith("--") else None
    col = "github-trending"
    if "--col" in argv:
        try:
            col = argv[argv.index("--col") + 1]
        except Exception:
            pass
    main(d, col)
