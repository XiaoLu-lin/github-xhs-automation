#!/usr/bin/env python3
"""中文富化：把 GitHub 仓库的英文介绍改写成中文，供日榜/周榜 build 之后调用。

两层策略：
  1) LLM 优先——读 config.json 的 ai 段（复用设置页已配的 OpenAI 兼容 key），
     让模型把每个仓库的英文简介翻成吸引人的中文短文案（tagline/problem/chips/code 说明）。
  2) 无 key 降级——用内置的「语言中文映射 + topics 中文映射 + 技术词表替换」拼出
     可读的中文介绍，保证满屏中文、不像纯英文那么突兀。

用法：
  from ai_cn import enrich_cn
  data = enrich_cn(data)   # data 是 build_from_trending 产出的 {"cover":..,"repos":[..],"follow":..}
  # 原地改写 repos 里每个仓库的 tagline_full / problem / chips / code_caption 为中文
"""
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DEFAULT_AI = {
    "base_url": "https://api.openai.com/v1",
    "api_key": "",
    "model": "gpt-4o",
    "prompt": "",
}


# ---------- 配置读取（与 server.py 约定一致：ROOT/config.json，缺省用 DEFAULT_AI）----------
def load_ai_cfg():
    cf = ROOT / "config.json"
    if cf.exists():
        try:
            cfg = json.loads(cf.read_text(encoding="utf-8"))
            return cfg.get("ai", {})
        except Exception:
            pass
    return dict(DEFAULT_AI)


# ---------- LLM 调用（OpenAI 兼容，复用设置页的 key）----------
def call_ai(system_prompt, user_content, ai):
    key = ai.get("api_key", "")
    if not key:
        raise ValueError("未配置 AI api_key（去设置页填写）")
    base = (ai.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    model = ai.get("model") or "gpt-4o"
    url = base + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.5,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read().decode("utf-8"))
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"AI 调用失败：{e}")


# ---------- 本地降级用映射表 ----------
LANG_CN = {
    "Python": "Python", "JavaScript": "JavaScript", "TypeScript": "TypeScript",
    "Shell": "Shell 脚本", "Rust": "Rust", "Go": "Go", "C++": "C++", "C": "C",
    "Java": "Java", "Ruby": "Ruby", "Lua": "Lua", "PHP": "PHP", "Swift": "Swift",
    "Kotlin": "Kotlin", "HTML": "HTML", "CSS": "CSS", "Vue": "Vue",
    "Svelte": "Svelte", "Jupyter Notebook": "Jupyter 笔记", "Other": "其他",
    "Zig": "Zig", "Dart": "Dart", "Scala": "Scala", "Elixir": "Elixir",
    "Objective-C": "Objective-C", "PowerShell": "PowerShell",
}

TOPIC_CN = {
    "machine-learning": "机器学习", "deep-learning": "深度学习", "ai": "人工智能",
    "artificial-intelligence": "人工智能", "llm": "大语言模型", "llms": "大语言模型",
    "gpt": "GPT", "agent": "智能体", "agents": "智能体", "agi": "通用人工智能",
    "chatbot": "聊天机器人", "rag": "检索增强生成", "nlp": "自然语言处理",
    "cv": "计算机视觉", "computer-vision": "计算机视觉",
    "python": "Python", "javascript": "JavaScript", "typescript": "TypeScript",
    "rust": "Rust", "go": "Go", "java": "Java", "c": "C", "cpp": "C++", "c++": "C++",
    "framework": "框架", "library": "库", "tool": "工具", "tools": "工具",
    "cli": "命令行工具", "api": "API", "sdk": "SDK", "plugin": "插件", "extension": "扩展",
    "web": "Web", "frontend": "前端", "backend": "后端", "fullstack": "全栈",
    "ui": "界面", "ux": "体验", "ui-components": "UI 组件",
    "automation": "自动化", "workflow": "工作流", "agentic": "智能体化", "mcp": "MCP 协议",
    "openai": "OpenAI", "github": "GitHub", "open-source": "开源", "opensource": "开源",
    "self-hosted": "自托管", "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
    "database": "数据库", "sql": "SQL", "nosql": "NoSQL", "redis": "Redis",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL", "sqlite": "SQLite", "mongodb": "MongoDB",
    "vision": "视觉", "image": "图像", "image-generation": "图像生成", "video": "视频",
    "audio": "音频", "speech": "语音", "tts": "语音合成", "asr": "语音识别",
    "prompt": "提示词", "prompt-engineering": "提示词工程", "embedding": "向量嵌入",
    "fine-tuning": "微调", "finetuning": "微调", "training": "训练", "inference": "推理",
    "browser": "浏览器", "browsing": "浏览", "scraping": "爬虫", "crawler": "爬虫",
    "search": "搜索", "search-engine": "搜索引擎", "realtime": "实时",
    "game": "游戏", "games": "游戏", "gaming": "游戏", "game-engine": "游戏引擎",
    "music": "音乐", "3d": "3D", "renderer": "渲染器", "rendering": "渲染", "engine": "引擎",
    "security": "安全", "encryption": "加密", "auth": "鉴权", "authentication": "鉴权",
    "authorization": "授权", "privacy": "隐私", "blockchain": "区块链",
    "productivity": "效率", "note-taking": "笔记", "notes": "笔记", "markdown": "Markdown",
    "obsidian": "Obsidian", "bot": "机器人", "discord": "Discord", "telegram": "Telegram",
    "slack": "Slack", "data": "数据", "data-science": "数据科学", "analytics": "分析",
    "visualization": "可视化", "dashboard": "仪表盘", "charts": "图表",
    "react": "React", "vue": "Vue", "nextjs": "Next.js", "nodejs": "Node.js",
    "node": "Node.js", "express": "Express", "django": "Django", "flask": "Flask",
    "testing": "测试", "ci": "持续集成", "devops": "DevOps", "monitoring": "监控",
    "translation": "翻译", "language": "语言", "chinese": "中文", "english": "英文",
    "documentation": "文档", "tutorial": "教程", "examples": "示例", "template": "模板",
    "starter": "入门模板", "boilerplate": "脚手架", "utils": "工具集", "utilities": "工具集",
    "helper": "辅助工具", "generator": "生成器", "builder": "构建器", "parser": "解析器",
    "compiler": "编译器", "interpreter": "解释器", "runtime": "运行时", "server": "服务端",
    "client": "客户端", "mobile": "移动端", "ios": "iOS", "android": "Android",
    "electron": "Electron", "desktop": "桌面端", "cross-platform": "跨平台",
    "performance": "性能", "optimization": "优化", "cache": "缓存", "concurrency": "并发",
    "multithreading": "多线程", "async": "异步", "grpc": "gRPC", "graphql": "GraphQL",
    "rest": "REST", "websocket": "WebSocket", "http": "HTTP", "proxy": "代理",
    "bot-framework": "机器人框架", "home-assistant": "Home Assistant", "iot": "物联网",
    "robotics": "机器人", "embedded": "嵌入式", "rpa": "流程自动化", "etl": "数据管道",
    "recommendation": "推荐", "recommender": "推荐系统", "knowledge-graph": "知识图谱",
    "summarization": "摘要", "agent-framework": "智能体框架", "multi-agent": "多智能体",
    "copilot": "副驾驶", "assistant": "助手", "codegen": "代码生成", "code-generation": "代码生成",
}

# description 技术词替换（英文 -> 中文），用词边界避免误伤
WORD_REPL = [
    ("artificial intelligence", "人工智能"), ("machine learning", "机器学习"),
    ("deep learning", "深度学习"), ("large language model", "大语言模型"),
    ("language model", "语言模型"), ("neural network", "神经网络"),
    ("natural language processing", "自然语言处理"), ("computer vision", "计算机视觉"),
    ("reinforcement learning", "强化学习"), ("generative", "生成式"),
    ("agent", "智能体"), ("framework", "框架"), ("library", "库"), ("tool", "工具"),
    ("command-line", "命令行"), ("command line", "命令行"), ("open source", "开源"),
    ("open-source", "开源"), ("self-hosted", "自托管"), ("real-time", "实时"),
    ("user interface", "用户界面"), ("out of the box", "开箱即用"),
    ("state of the art", "最先进"), ("easy to use", "简单易用"),
    ("high performance", "高性能"), ("production ready", "可用于生产"),
    ("for developers", "面向开发者"), ("in browser", "在浏览器中"),
    ("end to end", "端到端"), ("end-to-end", "端到端"), ("plug and play", "即插即用"),
    ("batteries included", "功能齐全"), ("lightweight", "轻量"), ("scalable", "可扩展"),
    ("cross-platform", "跨平台"), ("openai", "OpenAI"), ("github", "GitHub"),
    ("self-host", "自托管"), ("wrapper", "封装"), ("helper", "辅助"), ("utility", "工具"),
    ("boilerplate", "脚手架"), ("starter", "入门"), ("tutorial", "教程"),
    ("documentation", "文档"), ("community", "社区"), ("minimal", "极简"),
]


def _has_cn(s):
    return bool(s) and any("\u4e00" <= c <= "\u9fff" for c in s)


def _cn_ratio(s):
    """返回字符串中中文字符占比（0~1），用于判断「是否已基本中文化」。"""
    if not s:
        return 0.0
    cn = sum(1 for c in s if "\u4e00" <= c <= "\u9fff")
    return cn / max(1, len(s))


def _strip_trailing_en(s):
    """裁掉结尾的纯英文长串（中英对照简介里跟在中文后面的英文翻译），
    保留中文主体；对「以中文结尾」的正常文案无影响。"""
    if not s:
        return s
    cn_idx = [i for i, c in enumerate(s) if "\u4e00" <= c <= "\u9fff"]
    if not cn_idx:
        return s
    tail = s[cn_idx[-1] + 1:]
    if re.search(r"[A-Za-z]{8,}", tail):
        return s[: cn_idx[-1] + 1].rstrip(" ，。、")
    return s


def _translate_words(s):
    if not s:
        return s
    for en, zh in WORD_REPL:
        s = re.sub(r"(?i)\b" + re.escape(en) + r"\b", zh, s)
    return s


def _local_cn(repos):
    """本地降级（无 key 也全中文）：用结构化信号（语言/话题/星标）拼中文，
    完全不依赖英文描述——英文描述只做参考，绝不原样塞进展示文案。
    """
    for r in repos:
        # 先裁掉「中文 + 英文对照」尾巴里的纯英文翻译段，保留中文主体
        if r.get("problem"):
            r["problem"] = _strip_trailing_en(r["problem"])
        # problem 已大部分中文（手改/LLM/含术语的中文稿）→ 整条跳过，保留原样；
        # 仅「纯英文主导」的描述（中文占比 < 0.2）才走下方模板重新生成全中文
        prob0 = r.get("problem", "")
        if prob0 and _cn_ratio(prob0) >= 0.2:
            continue

        lang = r.get("lang") or "Other"
        lang_cn = LANG_CN.get(lang, "技术")
        if lang_cn == lang and not _has_cn(lang):  # 语言名不在映射里（仍是英文）
            lang_cn = "技术"

        # 话题 -> 中文：只保留能翻成中文的，丢弃英文残留
        raw_topics = [c for c in (r.get("chips") or []) if c and c != "开源"]
        seen = set()
        chips_cn = []
        for c in raw_topics:
            zh = TOPIC_CN.get(c, c)
            if _has_cn(zh) and zh not in seen:
                seen.add(zh)
                chips_cn.append(zh)
        if not chips_cn and _has_cn(lang_cn):
            chips_cn = [lang_cn]
        if not chips_cn:
            chips_cn = ["开源项目"]
        chips_cn = chips_cn[:5]
        # 去掉通用占位「技术」，避免「技术的技术」这类重复
        real_chips = [c for c in chips_cn if c != "技术"]

        today = r.get("today", "")
        today_cn = f"，本周新增 {today}★" if today and today != "—" else ""

        if real_chips:
            topic_phrase = "、".join(real_chips[:2])
            problem = (f"一个专注于{topic_phrase}的开源项目{today_cn}，"
                       f"已登上 GitHub 热榜，值得收藏。")
            tagline = f"{r['repo']}：{topic_phrase}开源项目"
        elif lang_cn != "技术":
            problem = f"一个{lang_cn}开源项目{today_cn}，已登上 GitHub 热榜，值得收藏。"
            tagline = f"{r['repo']}：{lang_cn}开源项目"
        else:
            problem = f"一个开源项目{today_cn}，已登上 GitHub 热榜，值得收藏。"
            tagline = f"{r['repo']}：开源项目"

        r["tagline_full"] = tagline
        r["problem"] = problem
        r["chips"] = real_chips if real_chips else ([lang_cn] if lang_cn != "技术" else ["开源项目"])
        # code_caption 本来就是中文（f"{lic} 开源 · 详见项目 README"），保留
    return repos


def _llm_cn(repos, ai):
    """LLM 优先：一次批量调用，返回精准中文。失败抛异常由上层降级。"""
    items = [
        {
            "rank": r.get("rank"),
            "repo": f"{r.get('owner')}/{r.get('repo')}",
            "lang": r.get("lang"),
            "desc": (r.get("problem") or r.get("description") or ""),
            "topics": [c for c in (r.get("chips") or []) if c and c != "开源"],
        }
        for r in repos
    ]
    system = (
        "你是小红书科技运营，把 GitHub 仓库的英文介绍改写成吸引人的中文短文案。"
        "仓库名(owner/repo)保持原文不翻译；介绍字段必须全中文，不得保留英文原文描述。"
        "只返回 JSON 数组，不要任何多余文字或代码围栏。"
        "每个元素字段："
        "tagline_cn(一句话亮点，≤18字)、"
        "problem_cn(中文简介，1-2句、30-45字，说清解决什么中文问题；必须完整收尾、不得截断，"
        "严禁出现'因字数限制已省略部分内容'之类的截断提示语)、"
        "chips_cn(3-5个中文标签的数组)、code_caption_cn(一句中文代码说明，≤22字)。"
    )
    user = json.dumps(items, ensure_ascii=False)
    txt = call_ai(system, user, ai)
    m = re.search(r"\[.*\]", txt, re.DOTALL)
    if not m:
        raise RuntimeError("AI 返回无法解析为 JSON 数组")
    arr = json.loads(m.group(0))
    by_rank = {a.get("rank"): a for a in arr if isinstance(a, dict)}
    for r in repos:
        a = by_rank.get(r.get("rank"))
        if not a:
            continue
        if a.get("tagline_cn"):
            r["tagline_full"] = a["tagline_cn"]
        if a.get("problem_cn"):
            r["problem"] = a["problem_cn"]
        if a.get("chips_cn") and isinstance(a["chips_cn"], list):
            r["chips"] = [str(x) for x in a["chips_cn"] if x][:5]
        if a.get("code_caption_cn"):
            r["code_caption"] = a["code_caption_cn"]
    return repos


def enrich_cn(data):
    """入口：把 data['repos'] 的英文介绍中文化（原地修改并返回）。"""
    repos = data.get("repos", [])
    if not repos:
        return data
    ai = load_ai_cfg()
    if ai.get("api_key"):
        try:
            _llm_cn(repos, ai)
            print("  [enrich_cn] 使用 LLM 精准中文翻译")
            return data
        except Exception as e:
            print(f"  [enrich_cn] LLM 翻译失败，降级本地模板：{e}")
        else:
            print("  [enrich_cn] 未检测到 AI key，使用本地中文模板降级")
    _local_cn(repos)
    return data


if __name__ == "__main__":
    # 自测：对现有周榜数据做一次中文化并预览前 2 条
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "data_weekly_2026-08-10.json"
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    enrich_cn(d)
    for r in d["repos"][:3]:
        print(f"#{r['rank']} {r['owner']}/{r['repo']}")
        print(f"  tagline: {r['tagline_full']}")
        print(f"  problem: {r['problem']}")
        print(f"  chips  : {r['chips']}")
