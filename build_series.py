#!/usr/bin/env python3
# build_series.py — 用 data JSON + template.html 生成当日 12 页系列 HTML
# 用法: python build_series.py <data.json> <out.html>
import json, html, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "template.html")


def esc(s):
    return html.escape(str(s), quote=True)


def render_stats(stats):
    cells = "".join(
        f'<div class="stat"><div class="v">{esc(s["v"])}</div><div class="k">{esc(s["k"])}</div></div>'
        for s in stats
    )
    return f'<div class="stats-row">{cells}</div>'


def render_chips(chips):
    out = []
    for c in chips:
        if isinstance(c, dict):
            cls = "chip w" if c.get("w") else "chip"
            out.append(f'<span class="{cls}">{esc(c["t"])}</span>')
        else:
            out.append(f'<span class="chip">{esc(c)}</span>')
    return f'<div class="chips">{"".join(out)}</div>'


def render_code(code, caption):
    lines = []
    for line in code:
        segs = []
        for typ, txt in line:
            if typ == "cm":
                segs.append(f'<span class="cm">{esc(txt)}</span>')
            elif typ == "c":
                segs.append(f'<span class="c">{esc(txt)}</span>')
            else:
                segs.append(esc(txt))
        lines.append("".join(segs))
    h = '<div class="code">' + "\n".join(lines)
    if caption:
        h += f'<div class="cap">{esc(caption)}</div>'
    h += "</div>"
    return h


def render_detail(r, period="今日"):
    rank = r["rank"]
    rank_label = f"TOP {rank:02d} / 10"
    full = esc(r["tagline_full"])
    hl = esc(r["tagline_hl"])
    tagline = full if not hl else full.replace(hl, f'<span class="accent">{hl}</span>')
    hero = f'''<div class="hero">
    <div class="lang"><span class="d" style="background:{esc(r["lang_color"])}"></span>{esc(r["lang"])}</div>
    <div class="rank"><small>{rank_label}</small>{rank:02d}</div>
    <div class="repo">{esc(r["repo"])}</div>
    <div class="owner">by <b>{esc(r["owner"])}</b> · {esc(r["author_note"])}</div>
  </div>'''
    body = f'''<div class="body">
    <div class="tagline">{tagline}</div>
    <div class="block">
      <div class="h"><span class="bar"></span>它解决什么问题</div>
      <div class="problem">{esc(r["problem"])}</div>
    </div>
    <div class="block">
      <div class="h"><span class="bar"></span>核心构成</div>
      {render_stats(r["stats"])}
    </div>
    <div class="block">
      <div class="h"><span class="bar"></span>关键特性</div>
      {render_chips(r["chips"])}
    </div>
    <div class="block">
      <div class="h"><span class="bar"></span>怎么用</div>
      {render_code(r["code"], r.get("code_caption"))}
    </div>
  </div>'''
    foot = f'''<div class="foot">
    <div class="big"><small>{period}新增 ★</small>{esc(r["today"])}</div>
    <div class="meta">★ 总 {esc(r["total"])}<br>GitHub {period}热榜 {esc(r["rank_no"])}</div>
    <div class="bar-track"><div class="bar-fill" style="width:{r["pct"]}%"></div></div>
  </div>'''
    return f'<div class="page">\n  {hero}\n  {body}\n  {foot}\n</div>'


def render_cover(d, period="今日", freq="每日"):
    hl = " · ".join(f"<b>{esc(n)}</b> {esc(t)}" for n, t in d["highlights"])
    return f'''<div class="page cover">
  <div class="badge">🔍 科技藏宝图 · {freq}更新</div>
  <div class="title">{period} GitHub<br>热点 Top 10</div>
  <div class="sub">全语言 Trending · {freq}挖出值得收藏的技术宝藏</div>
  <div class="date">{esc(d["date"])}</div>
  <div class="hero-num"><small>{period}全榜新增 ★</small>{esc(d["total_today"])}</div>
  <div class="ribbon">
    <div class="rcell"><div class="v">{esc(d["count"])}</div><div class="k">上榜项目</div></div>
    <div class="rcell"><div class="v">{esc(d["langs"])}</div><div class="k">编程语言</div></div>
    <div class="rcell"><div class="v">{esc(d["total_today"])}</div><div class="k">{period}新增星</div></div>
  </div>
  <div class="preview">本期亮点：{hl}</div>
  <div class="hint"><span class="d"></span>关注 @科技藏宝图，{freq} 1 分钟挖到好项目</div>
</div>'''


def render_follow(d):
    tags = "".join(f'<span>{esc(t)}</span>' for t in d["tags"])
    slogan = "<br>".join(esc(s) for s in d["slogan"])
    return f'''<div class="page follow">
  <div class="k">FOLLOW ME</div>
  <div class="handle"><span class="at">@</span>{esc(d["handle"])}</div>
  <div class="slogan">{slogan}</div>
  <div class="divider"></div>
  <div class="tags">{tags}</div>
  <div class="sign">{esc(d["sign"])}</div>
</div>'''


def build(data_path, out_path, period="今日", freq="每日"):
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)
    css = open(TPL, encoding="utf-8").read()
    pages = [render_cover(data["cover"], period, freq)] + [render_detail(r, period) for r in data["repos"]] + [render_follow(data["follow"])]
    doc = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>GitHub 热点 · 科技藏宝图 · Top10</title>
<style>
{css}
</style>
</head>
<body>
{chr(10).join(pages)}
</body>
</html>'''
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"built {out_path} ({len(pages)} pages)")


if __name__ == "__main__":
    data_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data_2026-08-09.json")
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "output", "2026-08-09", "github-xhs-series.html")
    period, freq = "今日", "每日"
    if "--period" in sys.argv:
        v = sys.argv[sys.argv.index("--period") + 1]
        if v == "weekly":
            period, freq = "本周", "每周"
    build(data_path, out_path, period, freq)
