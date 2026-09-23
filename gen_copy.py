#!/usr/bin/env python3
"""从当日 data_YYYY-MM-DD.json 生成小红书发布文案 copy.json。

输出：output/<date>/copy.json
字段：{ date, title, body, tags }
body 由真实仓库描述拼装（非编造），供控制台「一键复制」直接发小红书。

正文规则：
  - 主行用仓库「完整真实描述」(desc)，不截断词/句；超过预算时只在空格/标点处断。
  - 每条附一行真实数据（今日★ / 总星 / 协议），不写「因字数限制已省略」之类补丁语。
  - 总字数上限 1000（中文按字符计）。先全局收缩最长描述，仍超限则从末尾删除
    排名最低的条目（呈现“Top N”而非残缺“Top10”），绝不波及已写内容。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# 可作为断点的中英文标点 / 空白（用于安全截断，绝不在词中间硬切）
_BREAK = " ，。、；：!?；;:.,!? \n\t★·•·"


def _trim_safe(s, n):
    """把 s 收到 n 字以内，优先在空格/标点处断，绝不在词中间硬切。

    英文描述没有中文标点时退到最后一个空格（词边界）；都没有时才退到 n 处。
    断点后补「…」表示被收起，不输出任何“已省略”提示语。
    """
    if len(s) <= n:
        return s
    cut = s[:n]
    # 优先：在预算内最后一个标点/空格处断
    best = -1
    for ch in _BREAK:
        i = cut.rfind(ch)
        if i > best:
            best = i
    if best > n * 0.5:                 # 至少用掉一半预算，避免截得太短
        return s[:best].rstrip(_BREAK) + "…"
    # 退路：英文在 n 之前的最后一个空格（词边界）
    sp = cut.rfind(" ")
    if sp > n * 0.5:
        return s[:sp].rstrip(_BREAK) + "…"
    return cut.rstrip(_BREAK) + "…"


def _fmt_stat(r):
    """从结构化字段拼一行真实数据，绝不编造。"""
    parts = []
    today = r.get("today", "")
    total = r.get("total", "")
    lic = (r.get("author_note") or "").replace(" 开源", "").strip()
    if today and today != "—":
        parts.append(f"今日 {today}")
    if total:
        parts.append(f"总星 {total}")
    if lic:
        parts.append(lic)
    return " · ".join(parts)


def make_copy(date, repos, period="今日", freq="每天"):
    if not repos:
        return None
    word_day = "今天" if period == "今日" else "本周"
    word_freq = "每天" if freq == "每天" else "每周"

    # 标题：中文钩子，硬卡 ≤20 字（不塞英文仓库名长串）
    title = f"{period} GitHub 热点 Top10"
    if len(title) > 20:
        title = title[:20]

    LIMIT = 1000
    header = f"{word_day} GitHub 又刷出一堆狠货，直接上榜单 👇"
    footer = [
        f"{word_freq} 1 分钟，挖到值得收藏的技术宝藏 🔍",
        "关注 @科技藏宝图 ，技术干货不迷路～",
    ]

    # 同名仓库（如两个 skills）用 owner/repo 区分，避免正文里分不清
    repo_counts = {}
    for r in repos:
        repo_counts[r.get("repo", "")] = repo_counts.get(r.get("repo", ""), 0) + 1

    entries = []
    for r in repos:
        rank = r.get("rank", "")
        repo = r.get("repo", "")
        owner = r.get("owner", "")
        label = f"{owner}/{repo}" if repo_counts.get(repo, 0) > 1 else repo
        desc = (r.get("desc") or "").strip()
        if not desc:
            # 无真实描述：退而用语言/话题推导一句事实文案（不编造“开源项目”废话）
            lang = r.get("lang") or ""
            chips = [c for c in (r.get("chips") or [])
                     if c and c not in ("开源", "开源项目") and "开源" not in c]
            if chips:
                desc = f"{lang} 项目，聚焦 {chips[0]}"
            else:
                desc = f"{lang} 开源项目" if lang else "开源项目"
        entries.append({
            "prefix": f"{rank}. {label}｜",
            "desc": desc,
            "stat": _fmt_stat(r),
            "cut": None,            # None = 不收缩；整数 = 收缩到该字数
        })

    def _render():
        out = []
        for e in entries:
            d = e["desc"] if e["cut"] is None else _trim_safe(e["desc"], e["cut"])
            out.append(f"{e['prefix']}{d}")
            if e["stat"]:
                out.append(f"   ⭐ {e['stat']}")
        return "\n".join(out)

    def _assemble(block):
        return f"{header}\n\n{block}\n\n" + "\n".join(footer)

    # 给结尾 footer 预留固定空间：footer 永远整段保留，不进入压缩/截断逻辑。
    footer_len = sum(len(f) for f in footer) + len(footer)  # 各 footer 行 + 换行
    overhead = len(header) + 4 + footer_len
    budget = LIMIT - overhead
    if budget < 200:
        budget = 200

    block = _render()
    # 有界循环：整体超预算时，从当前最长描述开始逐步收缩（词/句边界安全）
    for _ in range(400):
        if len(block) <= budget:
            break
        cand = max(entries, key=lambda e: len(e["desc"]) if e["cut"] is None else e["cut"])
        cur = len(cand["desc"]) if cand["cut"] is None else cand["cut"]
        if cur <= 16:               # 已无可压缩空间，交给下方删条目兜底
            break
        cand["cut"] = max(16, cur - 4)
        block = _render()

    body = _assemble(block)
    # 兜底 1：仅裁条目块尾部，在最后一个完整句/词边界断开，绝不词中硬切、绝不波及 footer
    if len(body) > LIMIT:
        excess = len(body) - LIMIT
        cut = len(block) - excess
        bp = -1
        for i in range(cut, -1, -1):
            if block[i] in _BREAK:
                bp = i
                break
        block = block[:bp].rstrip(_BREAK) if bp > 0 else block[:cut].rstrip(_BREAK)
        body = _assemble(block)

    # 兜底 2：极端情况下，从末尾删除排名最低的整条，呈现“Top N”而非残缺“Top10”
    while len(body) > LIMIT and len(entries) > 1:
        entries.pop()
        block = _render()
        body = _assemble(block)

    tags = ["#GitHub热点", "#开源", "#AI", "#程序员", "#科技藏宝图"]
    return {"date": date, "title": title, "body": body, "tags": tags}


def main(date=None, out_dir=None, period="今日"):
    if date:
        data_file = ROOT / f"data_{date}.json"
    else:
        files = sorted(ROOT.glob("data_*.json"))
        if not files:
            print("未找到 data_*.json")
            return
        data_file = files[-1]
    if not data_file.exists():
        print(f"数据文件不存在: {data_file}")
        return

    m = re.search(r"data_(.+)\.json", data_file.name)
    date = m.group(1)
    data = json.loads(data_file.read_text(encoding="utf-8"))
    repos = data.get("repos", [])
    if not repos:
        print("数据中没有 repos")
        return

    p = period
    fq = "每周" if p == "本周" else "每天"
    copy = make_copy(date, repos, p, fq)
    if not copy:
        return

    out_dir = Path(out_dir) if out_dir else (ROOT / "output" / date)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "copy.json").write_text(
        json.dumps(copy, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已生成 {out_dir / 'copy.json'}  (正文 {len(copy['body'])} 字)")


if __name__ == "__main__":
    argv = sys.argv[1:]
    date = argv[0] if argv and not argv[0].startswith("--") else None
    out_dir = None
    period = "今日"
    if "--out" in argv:
        try:
            out_dir = argv[argv.index("--out") + 1]
        except Exception:
            pass
    if "--period" in argv:
        try:
            v = argv[argv.index("--period") + 1]
            if v == "weekly":
                period = "本周"
        except Exception:
            pass
    main(date, out_dir, period)
