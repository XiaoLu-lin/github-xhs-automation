#!/usr/bin/env python3
"""发布控制台本地小服务。

- 提供单页控制台 console.html
- 提供 API 读取 columns.json + output/<栏目>/<日期>/ 下的生成物
- 新增：总览聚合 / 历史索引 / 自动化状态 / 立即运行 / 配置 / 栏目管理
- 静态服务 output/ 下的 PNG / HTML，供「查看图」使用

零三方依赖，仅用标准库。运行：python3 server.py
"""
import json
import re
import os
import sys
import csv
import io
import subprocess
import mimetypes
import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent          # github-xhs-automation
COLUMNS_FILE = ROOT / "columns.json"
PORT = 8787

DEFAULT_CONFIG = {
    "account": "科技藏宝图",
    "copy_template": {
        "title": "GitHub 今日热点 Top10｜{top1} 登顶",
        "body": "今天 GitHub 又刷出一堆狠货，直接上榜单 👇\n\n（逐条仓库 + 一句话）\n\n每天 1 分钟，挖到值得收藏的技术宝藏 🔍\n关注 @科技藏宝图 ，技术干货不迷路～",
        "tags": ["#GitHub热点", "#开源", "#AI", "#程序员", "#科技藏宝图"],
    },
    "compliance": [
        "翻墙", "科学上网", "fanqiang", "fuckgfw", "vpn", "proxy", "trojan",
        "ssr", "v2ray", "shadowsocks", "bannedbook", "自由门", "无界",
        "lantern", "psiphon", "赛风", "突破封锁", "gfw", "circumvent",
    ],
    "ai": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "model": "gpt-4o",
        "prompt": "你是「科技藏宝图」的小红书运营专家，拥有 5 年以上经验，擅长把 GitHub/技术内容改写成高互动的小红书笔记与运营复盘。\n\n【身份与风格】\n- 简体中文，口语化、有网感，适当用 emoji 增强可读性\n- 重点前置、条理清晰，不堆砌、不啰嗦\n- 只基于用户提供的信息延展，绝不编造数据或事实\n\n【小红书平台发布规范】（生成笔记或发布文案时务必遵守）\n- 标题：不超过 20 个汉字（含标点），要有钩子，带数字、冲突感或结果导向\n- 正文：不超过 1000 字，分段清晰，结尾加互动引导，例如关注我每天 1 分钟挖到好项目\n- 合理带话题标签 #xxx\n\n【输出要求】\n- 具体写什么、什么结构，以我每次给你的指令为准\n- 若要求 Markdown，则一级标题用 #、小节用 ##",
    },
}


# ---------- 基础读取 ----------
def load_columns():
    return json.loads(COLUMNS_FILE.read_text(encoding="utf-8"))


def col_output_dir(col):
    return ROOT / col["output_dir"]


def find_col(cid):
    return next((c for c in load_columns()["columns"] if c["id"] == cid), None)


def list_articles(col):
    d = col_output_dir(col)
    if not d.exists():
        return []
    res = []
    for date_dir in sorted(d.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        png_dir = date_dir / "png"
        pngs = list(png_dir.glob("*.png")) if png_dir.exists() else []
        res.append({
            "date": date_dir.name,
            "pages": len(pngs),
            "has_copy": (date_dir / "copy.json").exists(),
            "has_html": (date_dir / "github-xhs-series.html").exists(),
            "status": pub_status(col, date_dir.name),
        })
    return res


def load_index(col, date):
    fp = col_output_dir(col) / date / "index.json"
    if fp.exists():
        return json.loads(fp.read_text(encoding="utf-8"))
    return None


def pub_status(col, date):
    """每期内容的发布状态：generated 但无 status.json → pending；已写 status.json → 取其值；未生成 → none。"""
    d = col_output_dir(col) / date
    has = (d / "copy.json").exists() or (d / "github-xhs-series.html").exists()
    sf = d / "status.json"
    if sf.exists():
        try:
            s = json.loads(sf.read_text(encoding="utf-8"))
            st = s.get("status")
            if st in ("pending", "published"):
                return st
        except Exception:
            pass
    return "pending" if has else "none"


def status_file(col, date):
    return col_output_dir(col) / date / "status.json"


def load_status(col, date):
    fp = status_file(col, date)
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def open_folder(path):
    """在本机文件管理器中打开目录（仅 localhost 本机服务有意义）。"""
    path = str(path)
    if not os.path.exists(path):
        return False
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        elif sys.platform == "win32":
            subprocess.run(["explorer", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
        return True
    except Exception:
        return False


def get_article(col, date):
    d = col_output_dir(col) / date
    copy = None
    cf = d / "copy.json"
    if cf.exists():
        copy = json.loads(cf.read_text(encoding="utf-8"))
    pngs = []
    png_dir = d / "png"
    if png_dir.exists():
        pngs = [f"/output/{col['output_dir']}/{date}/png/{p.name}"
                for p in sorted(png_dir.glob("*.png"))]
    html = (f"/output/{col['output_dir']}/{date}/github-xhs-series.html"
            if (d / "github-xhs-series.html").exists() else None)
    tasks = {
        "抓取": (d / "github-xhs-series.html").exists() or (d / "copy.json").exists(),
        "生成": (d / "copy.json").exists(),
        "渲染": len(pngs) > 0,
        "合规": True,
    }
    st = load_status(col, date)
    return {"date": date, "copy": copy, "pngs": pngs, "html": html, "tasks": tasks,
            "status": pub_status(col, date),
            "planned_at": st.get("planned_at", ""),
            "note": st.get("note", "")}


def to_int_star(s):
    if not s:
        return 0
    return int(re.sub(r"[^\d]", "", str(s)) or 0)


# ---------- 新增聚合接口 ----------
def get_overview():
    cols = load_columns()
    columns_out = []
    dates_set = set()
    total_issues = 0
    for c in cols["columns"]:
        arts = list_articles(c)
        total_issues += len(arts)
        latest = arts[0]["date"] if arts else None
        columns_out.append({
            "id": c["id"], "name": c["name"], "icon": c.get("icon"),
            "color": c.get("color"), "status": c.get("status", "active"),
            "schedule": c.get("schedule"), "article_count": len(arts),
            "latest": latest,
        })
        for a in arts:
            dates_set.add(a["date"])
    # 近 7 日每日新增星（跨栏目聚合）
    agg = {}
    for c in cols["columns"]:
        for a in list_articles(c):
            idx = load_index(c, a["date"])
            if idx:
                agg[a["date"]] = agg.get(a["date"], 0) + to_int_star(idx["meta"].get("total_today", ""))
    trend = [{"date": d, "total_today": agg[d]} for d in sorted(agg)]
    week_stars = sum(v for _, v in list(sorted(agg.items()))[-7:])
    return {
        "account": cols.get("account"),
        "columns": columns_out,
        "dates": sorted(dates_set),
        "trend": trend,
        "totals": {
            "columns": len(cols["columns"]),
            "issues": total_issues,
            "week_stars": week_stars,
            "pending": sum(1 for c in cols["columns"] for a in list_articles(c) if a.get("status") == "pending"),
        },
    }


def get_history(col_id, limit=60):
    col = find_col(col_id)
    if not col:
        return []
    out = []
    for a in list_articles(col)[:limit]:
        idx = load_index(col, a["date"])
        if idx:
            out.append(idx)
    return out


def get_calendar(year, month):
    cols = load_columns()["columns"]
    issues = []
    for c in cols:
        for a in list_articles(c):
            st = load_status(c, a["date"])
            issues.append({
                "col": c["id"], "col_name": c.get("name"),
                "col_color": c.get("color"), "date": a["date"],
                "status": a["status"],
                "planned_at": st.get("planned_at", ""),
                "note": st.get("note", ""),
                "pages": a["pages"], "has_copy": a["has_copy"],
            })
    return {"year": year, "month": month, "issues": issues}


def get_all_issues():
    """跨栏目汇总所有期次（内容发布页统一队列用），不限月份。"""
    cols = load_columns()["columns"]
    issues = []
    for c in cols:
        for a in list_articles(c):
            st = load_status(c, a["date"])
            issues.append({
                "col": c["id"], "col_name": c.get("name"),
                "col_color": c.get("color"), "date": a["date"],
                "status": a["status"],
                "planned_at": st.get("planned_at", ""),
                "note": st.get("note", ""),
                "pages": a["pages"], "has_copy": a["has_copy"],
            })
    issues.sort(key=lambda x: x["date"], reverse=True)
    return {"issues": issues}


def get_automations():
    cols = load_columns()
    tasks = []
    for c in cols["columns"]:
        if c.get("status") == "configuring":
            continue
        tasks.append({
            "id": c["id"], "name": c["name"], "schedule": c.get("schedule"),
            "source": c.get("source"), "status": c.get("status", "active"),
        })
    run_log = None
    rlf = ROOT / "run_log.json"
    if rlf.exists():
        try:
            run_log = json.loads(rlf.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"tasks": tasks, "run_log": run_log}


def run_now():
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "generate_daily.py")],
            capture_output=True, text=True, timeout=300,
        )
        rlf = ROOT / "run_log.json"
        log = json.loads(rlf.read_text(encoding="utf-8")) if rlf.exists() else {"status": "unknown"}
        return {
            "returncode": proc.returncode,
            "log": log,
            "stdout_tail": proc.stdout[-1000:],
            "stderr": proc.stderr[-1000:],
        }
    except Exception as e:
        return {"returncode": -1, "error": str(e)}


def read_config():
    cf = ROOT / "config.json"
    if cf.exists():
        try:
            return json.loads(cf.read_text(encoding="utf-8"))
        except Exception:
            pass
    return DEFAULT_CONFIG


def write_config(cfg):
    (ROOT / "config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- 数据复盘（上传 + AI 生成） ----------
REVIEW_DATA_FILE = ROOT / "review_data.json"
REVIEW_REPORTS_FILE = ROOT / "review_reports.json"

# 列名 → 标准字段 的模糊映射
_COL_RULES = {
    "title": ["标题", "title", "题目", "note", "笔记"],
    "date": ["发布日期", "日期", "date", "时间", "发布时间"],
    "reads": ["阅读量", "阅读", "read", "reads", "播放", "plays", "曝光", "展现"],
    "likes": ["点赞", "赞", "like", "likes"],
    "favorites": ["收藏", "藏", "favorite", "favourite", "collect", "favorites"],
    "comments": ["评论", "评", "comment", "comments"],
    "followers": ["涨粉", "粉丝", "follower", "followers", "fans", "新增粉丝"],
    "tags": ["标签", "tag", "tags", "话题", "topic"],
}


def _col_map(headers):
    m = {}
    for i, h in enumerate(headers):
        hl = (h or "").strip().lower()
        for std, kws in _COL_RULES.items():
            if any(k.lower() in hl for k in kws):
                m[std] = i
                break
    return m


def parse_review_csv(text):
    """解析用户上传的运营 CSV → 标准行列表。容错中英文表头。"""
    reader = list(csv.reader(io.StringIO(text)))
    reader = [r for r in reader if any(c.strip() for c in r)]
    if len(reader) < 2:
        return []
    m = _col_map(reader[0])

    def get(r, f):
        i = m.get(f)
        return r[i].strip() if (i is not None and i < len(r)) else ""

    out = []
    for r in reader[1:]:
        tags = [t.strip() for t in re.split(r"[|,、]", get(r, "tags")) if t.strip()]
        out.append({
            "title": get(r, "title"),
            "date": get(r, "date"),
            "reads": to_int_star(get(r, "reads")),
            "likes": to_int_star(get(r, "likes")),
            "favorites": to_int_star(get(r, "favorites")),
            "comments": to_int_star(get(r, "comments")),
            "followers": to_int_star(get(r, "followers")),
            "tags": tags,
        })
    return out


def compute_review_metrics(rows):
    n = len(rows)
    if not n:
        return {"count": 0}
    tot = lambda f: sum(r[f] for r in rows)
    tr, tl, tf, tc, tfo = tot("reads"), tot("likes"), tot("favorites"), tot("comments"), tot("followers")
    interaction = tl + tf + tc
    avg_ir = round(interaction / tr * 100, 2) if tr else 0
    by_reads = sorted(rows, key=lambda r: r["reads"], reverse=True)[:10]
    by_date = {}
    for r in rows:
        d = by_date.setdefault(r["date"], {"reads": 0, "followers": 0, "count": 0})
        d["reads"] += r["reads"]; d["followers"] += r["followers"]; d["count"] += 1
    trend = [{"date": k, **v} for k, v in sorted(by_date.items())]
    tag_map = {}
    for r in rows:
        for t in r["tags"]:
            tg = tag_map.setdefault(t, {"reads": 0, "count": 0, "interaction": 0})
            tg["reads"] += r["reads"]; tg["count"] += 1
            tg["interaction"] += r["likes"] + r["favorites"] + r["comments"]
    tag_rows = sorted(
        [{"tag": t, **v, "avg_reads": (v["reads"] // v["count"] if v["count"] else 0)}
         for t, v in tag_map.items()],
        key=lambda x: x["avg_reads"], reverse=True)
    return {
        "count": n,
        "totals": {"reads": tr, "likes": tl, "favorites": tf, "comments": tc,
                   "followers": tfo, "interaction": interaction},
        "avg_reads": tr // n,
        "avg_interaction_rate": avg_ir,
        "top_by_reads": [{"title": r["title"], "reads": r["reads"], "likes": r["likes"],
                          "favorites": r["favorites"], "comments": r["comments"],
                          "followers": r["followers"], "tags": r["tags"], "date": r["date"]} for r in by_reads],
        "trend": trend,
        "tags": tag_rows,
    }


def save_review_data(rows):
    REVIEW_DATA_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def load_review_data():
    if REVIEW_DATA_FILE.exists():
        try:
            return json.loads(REVIEW_DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_review_report(markdown, summary, model):
    reports = []
    if REVIEW_REPORTS_FILE.exists():
        try:
            reports = json.loads(REVIEW_REPORTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            reports = []
    rid = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    reports.insert(0, {
        "id": rid,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "model": model,
        "summary": summary,
        "markdown": markdown,
    })
    REVIEW_REPORTS_FILE.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    return rid


def load_review_reports():
    if REVIEW_REPORTS_FILE.exists():
        try:
            return json.loads(REVIEW_REPORTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def build_review_prompt(metrics):
    """方案 A：用户配的是人设/风格，系统拼装结构化数据喂给 AI。"""
    m = metrics
    lines = []
    lines.append(f"以下是我的小红书笔记运营数据（共 {m['count']} 篇）：")
    lines.append("")
    lines.append("【整体指标】")
    lines.append(f"总笔记数：{m['count']}")
    lines.append(f"总阅读量：{m['totals']['reads']:,}")
    lines.append(f"总点赞：{m['totals']['likes']:,}  总收藏：{m['totals']['favorites']:,}  总评论：{m['totals']['comments']:,}")
    lines.append(f"总涨粉：{m['totals']['followers']:,}")
    lines.append(f"平均阅读量：{m['avg_reads']:,}  平均互动率：{m['avg_interaction_rate']}%")
    lines.append("")
    lines.append("【爆款 Top5（按阅读量）】")
    for i, r in enumerate(m["top_by_reads"][:5], 1):
        tags = " / ".join(r["tags"]) or "—"
        lines.append(f"{i}. {r['title']} — 阅读 {r['reads']:,} / 赞 {r['likes']:,} / 藏 {r['favorites']:,} / 评 {r['comments']:,} / 涨粉 {r['followers']:,} ｜ 标签：{tags}")
    lines.append("")
    lines.append("【各标签表现（按平均阅读）】")
    for t in m["tags"][:10]:
        lines.append(f"- {t['tag']}：{t['count']} 篇，平均阅读 {t['avg_reads']:,}，总互动 {t['interaction']:,}")
    lines.append("")
    lines.append("请基于以上数据，输出复盘报告。")
    return "\n".join(lines)


def call_ai(system_prompt, user_content, cfg):
    """调 OpenAI 兼容 Chat Completions，返回文本。失败抛异常。"""
    ai = cfg.get("ai", {})
    key = ai.get("api_key", "")
    if not key:
        raise ValueError("未配置 AI api_key（去设置页填写）")
    base = (ai.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    model = ai.get("model") or "gpt-4o"
    url = base + "/chat/completions"
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.7,
    }
    req = urllib.request.Request(
        url, data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read().decode("utf-8"))
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"AI 调用失败：{e}")


# ---------- 复盘记录（历史报告浏览） ----------
def get_reviews():
    """读取 reviews/ 下所有 *.html 复盘报告，按文件名日期 + 页面 <title> 列出。"""
    d = ROOT / "reviews"
    if not d.exists():
        return []
    out = []
    for f in sorted(d.glob("*.html"), reverse=True):
        date = f.stem
        title = date
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"<title>(.*?)</title>", txt, re.S)
            if m:
                title = m.group(1).strip()
        except Exception:
            pass
        out.append({"date": date, "title": title})
    return out


# ---------- HTTP ----------
class Handler(SimpleHTTPRequestHandler):
    def _send(self, payload, ctype="application/json; charset=utf-8", code=200):
        if isinstance(payload, (dict, list)):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        else:
            body = payload.encode("utf-8") if isinstance(payload, str) else payload
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        return {}

    def do_GET(self):
        p = urlparse(self.path)
        path = p.path

        if path in ("/", "/console.html"):
            self._send((ROOT / "console.html").read_bytes(), "text/html; charset=utf-8")
            return

        if path == "/api/columns":
            cols = load_columns()
            out = {"account": cols.get("account"), "columns": []}
            for c in cols["columns"]:
                arts = list_articles(c)
                out["columns"].append({
                    "id": c["id"], "name": c["name"], "icon": c.get("icon"),
                    "color": c.get("color"), "source": c.get("source"),
                    "schedule": c.get("schedule"),
                    "status": c.get("status", "active"),
                    "article_count": len(arts),
                    "latest": arts[0]["date"] if arts else None,
                })
            self._send(out)
            return

        if path == "/api/articles":
            cid = parse_qs(p.query).get("col", [""])[0]
            col = find_col(cid)
            if not col:
                self._send({"error": "栏目不存在"}, code=404)
                return
            self._send({"column": cid, "articles": list_articles(col)})
            return

        if path == "/api/article":
            q = parse_qs(p.query)
            cid, dt = q.get("col", [""])[0], q.get("date", [""])[0]
            col = find_col(cid)
            if not col:
                self._send({"error": "栏目不存在"}, code=404)
                return
            self._send(get_article(col, dt))
            return

        if path == "/api/overview":
            self._send(get_overview())
            return

        if path == "/api/calendar":
            q = parse_qs(p.query)
            m = q.get("month", [""])[0]
            if m and re.match(r"^\d{4}-\d{2}$", m):
                y, mo = int(m[:4]), int(m[5:7])
            else:
                t = datetime.date.today()
                y, mo = t.year, t.month
            self._send(get_calendar(y, mo))
            return

        if path == "/api/issues":
            self._send(get_all_issues())
            return

        if path == "/api/history":
            q = parse_qs(p.query)
            cid = q.get("col", ["github-trending"])[0]
            limit = int(q.get("limit", ["60"])[0])
            self._send({"column": cid, "history": get_history(cid, limit)})
            return

        if path == "/api/automations":
            self._send(get_automations())
            return

        if path == "/api/config":
            self._send(read_config())
            return

        if path == "/api/review-data":
            q = parse_qs(p.query)
            rows = load_review_data()
            def norm(s): return (s or "").replace("/", "-")

            frm = norm(q.get("from", [""])[0].strip())
            to = norm(q.get("to", [""])[0].strip())
            if frm or to:
                rows = [r for r in rows
                        if (not frm or norm(r["date"]) >= frm)
                        and (not to or norm(r["date"]) <= to)]
            self._send({"rows": rows, "metrics": compute_review_metrics(rows)})
            return

        if path == "/api/review-reports":
            self._send({"reports": load_review_reports()})
            return

        if path == "/api/reviews":
            self._send({"reviews": get_reviews()})
            return

        if path == "/api/review-template":
            csv_text = "﻿标题,发布日期,阅读量,点赞,收藏,评论,涨粉,标签\n示例：GitHub热点Top10怎么用,2026-08-09,12000,800,300,50,120,AI|开源|GitHub\n"
            self._send(csv_text, "text/csv; charset=utf-8")
            return

        if path == "/api/open-folder":
            q = parse_qs(p.query)
            cid = q.get("col", [""])[0]
            dt = q.get("date", [""])[0]
            which = q.get("which", ["png"])[0]
            col = find_col(cid)
            if not col:
                self._send({"error": "栏目不存在"}, code=404)
                return
            base = col_output_dir(col) / dt
            target = base if which == "root" else (base / which)
            if not target.exists():
                target = base
            ok = open_folder(target)
            self._send({"ok": ok, "path": str(target)})
            return

        if path.startswith("/output/"):
            fp = ROOT / path[len("/output/"):]
            if fp.exists() and fp.is_file():
                ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
                self._send(fp.read_bytes(), ctype)
                return

        if path.startswith("/reviews/"):
            fp = ROOT / "reviews" / path[len("/reviews/"):]
            if fp.exists() and fp.is_file():
                ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
                self._send(fp.read_bytes(), ctype)
                return

        self.send_error(404)

    def do_POST(self):
        p = urlparse(self.path)
        path = p.path
        if path == "/api/run":
            self._send(run_now())
            return
        if path == "/api/config":
            cfg = self._body()
            write_config(cfg)
            self._send({"ok": True})
            return
        if path == "/api/columns":
            cfg = self._body()
            (ROOT / "columns.json").write_text(
                json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            self._send({"ok": True})
            return
        if path == "/api/status":
            b = self._body()
            col = find_col(b.get("col", ""))
            if not col:
                self._send({"error": "栏目不存在"}, code=404)
                return
            date = b.get("date", "")
            status = b.get("status", "pending")
            if status not in ("pending", "published"):
                status = "pending"
            dd = col_output_dir(col) / date
            if not dd.exists():
                self._send({"error": "该期不存在"}, code=404)
                return
            st = load_status(col, date)
            st["status"] = status
            st["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            if "planned_at" in b:
                st["planned_at"] = (b.get("planned_at") or "").strip()
            if "note" in b:
                st["note"] = b.get("note") or ""
            (dd / "status.json").write_text(
                json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
            self._send({"ok": True, "status": status,
                        "planned_at": st.get("planned_at", ""),
                        "note": st.get("note", "")})
            return

        if path == "/api/review-upload":
            b = self._body()
            rows = parse_review_csv(b.get("csv", ""))
            if not rows:
                self._send({"error": "未解析到数据，请检查 CSV 表头（需含 标题/阅读量 等列）"}, code=400)
                return
            save_review_data(rows)
            self._send({"ok": True, "count": len(rows), "metrics": compute_review_metrics(rows)})
            return

        if path == "/api/review-ai":
            cfg = read_config()
            b = self._body()
            rows = load_review_data()
            if not rows:
                self._send({"error": "请先上传运营数据"}, code=400)
                return
            if not cfg.get("ai", {}).get("api_key"):
                self._send({"error": "未配置 AI api_key，去设置页填写"}, code=400)
                return
            def norm(s): return (s or "").replace("/", "-")
            frm = norm(b.get("from", "")); to = norm(b.get("to", ""))
            if frm or to:
                rows = [r for r in rows
                        if (not frm or norm(r["date"]) >= frm)
                        and (not to or norm(r["date"]) <= to)]
            metrics = compute_review_metrics(rows)
            prompt = build_review_prompt(metrics)
            try:
                md = call_ai(cfg["ai"].get("prompt", ""), prompt, cfg)
            except Exception as e:
                self._send({"error": str(e)}, code=500)
                return
            scope = (f" {frm}~{to}" if (frm or to) else "")
            rid = save_review_report(md, f"共 {metrics['count']} 篇笔记复盘{scope}", cfg["ai"].get("model", ""))
            self._send({"ok": True, "markdown": md, "id": rid,
                        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")})
            return

        if path == "/api/review-report":
            b = self._body()
            rid = save_review_report(b.get("markdown", ""), b.get("summary", ""), b.get("model", ""))
            self._send({"ok": True, "id": rid})
            return
        self.send_error(404)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"发布控制台已启动 → http://127.0.0.1:{PORT}")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
