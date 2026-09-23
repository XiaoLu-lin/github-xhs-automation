#!/usr/bin/env python3
"""从当日 data_YYYY-MM-DD.json 生成小红书发布文案 copy.json。

输出：output/<date>/copy.json
字段：{ date, title, body, tags }
body 由真实仓库 tagline 拼装（非编造事实），供控制台「一键复制」直接发小红书。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _first_sentence(s, n):
    """把 s 截到 n 字以内，优先在句末/分句标点处断，保证是一句完整的话；
    绝不在词中间硬切，也不输出「因字数限制已省略」之类的补丁语。"""
    if len(s) <= n:
        return s
    cut = -1
    for i, ch in enumerate(s):
        if ch in "。！？；，" and i <= n:
            cut = i + 1
    if cut > 0:
        return s[:cut].rstrip("，、； ")
    return s[:n].rstrip("，、； ")


def _strip_repo_prefix(tag, repo):
    """tagline_full 惯例以「repo：」开头，而正文行前缀已展示仓库名。

    去掉这段重复既避免「repo｜repo…」的观感，也把预算让给真正的中文简介。
    """
    t = (tag or "").strip()
    for sep in ("：", ":"):
        p = f"{repo}{sep}"
        if t.startswith(p):
            return t[len(p):].strip()
    return t


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
    # 预算按「全局」分配而非平分：先假设每条都写全，只有整体超 1000 字时，
    # 才从当前最长的 tagline 开始逐步收缩。避免总量明明够、个别条目却被截断。
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
        prob = r.get("problem", "")
        entries.append({
            "prefix": f"{rank}. {label}｜",
            "tag": _strip_repo_prefix(r.get("tagline_full", ""), repo),
            "line2": f"   {prob}" if prob else "",
            "cut": None,          # None = 不收缩；整数 = 收缩到该字数
        })

    def _shrink(tag, n):
        """收缩到 n 字以内，优先在标点处断，never 词中硬切。"""
        if len(tag) <= n:
            return tag
        cut = -1
        for i, ch in enumerate(tag):
            if ch in "：:，,；;、" and i <= n:
                cut = i
        t = tag[:cut] if cut > 0 else tag[:n]
        return f"{t.rstrip('，、：: ')}…"

    def _render_entries():
        """只渲染仓库条目块（不含标题行与结尾 footer），便于单独控预算。"""
        out = []
        for e in entries:
            tag = e["tag"] if e["cut"] is None else _shrink(e["tag"], e["cut"])
            out.append(f"{e['prefix']}{tag}")
            if e["line2"]:
                out.append(e["line2"])
        return "\n".join(out)

    def _assemble(entries_block):
        return f"{header}\n\n{entries_block}\n\n" + "\n".join(footer)

    # 给结尾 footer 预留固定空间：footer 永远整段保留，不进入压缩/截断逻辑。
    footer_len = sum(len(f) for f in footer) + len(footer)  # 各 footer 行 + 换行
    overhead = len(header) + 4 + footer_len                  # 标题行 + 空行 + footer 区
    budget = LIMIT - overhead
    if budget < 200:
        budget = 200

    entries_block = _render_entries()
    for _ in range(400):                      # 有界循环，防御性上限
        if len(entries_block) <= budget:
            break
        cand = max(entries, key=lambda e: len(e["tag"]) if e["cut"] is None else e["cut"])
        cur = len(cand["tag"]) if cand["cut"] is None else cand["cut"]
        if cur <= 12:                         # 已无可压缩空间，交给下方兜底
            break
        cand["cut"] = max(12, cur - 4)
        entries_block = _render_entries()

    body = _assemble(entries_block)
    # 兜底：仅裁仓库条目块尾部，绝不波及 footer（绝不出现「因字数限制已省略」）
    # 关键：在最后一个完整句/分句处断开，绝不词中硬切，保证读来是一篇完整的话
    if len(body) > LIMIT:
        excess = len(body) - LIMIT
        cut = len(entries_block) - excess
        bp = -1
        for i in range(cut, -1, -1):
            if entries_block[i] in "。！？；，、 \n":
                bp = i
                break
        if bp > 0:
            entries_block = entries_block[:bp].rstrip("，、； \n")
        else:
            entries_block = entries_block[:cut].rstrip("，、； \n")
        body = _assemble(entries_block)

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
    print(f"已生成 {out_dir / 'copy.json'}")


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
