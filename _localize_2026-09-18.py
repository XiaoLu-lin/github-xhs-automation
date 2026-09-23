#!/usr/bin/env python3
"""一次性脚本：把 data_2026-09-18.json 的 10 个仓库中文化写回。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
f = ROOT / "data_2026-09-18.json"
data = json.loads(f.read_text(encoding="utf-8"))

# 每个仓库的中文化字段（tagline_hl 必须是 tagline_full 的连续子串）
updates = {
    "alibaba/open-code-review": dict(
        tagline_full="阿里开源的混合架构代码审查工具：确定性流水线 + LLM 智能体",
        tagline_hl="代码审查",
        problem="解决大厂代码评审慢、标准不一的难题：规则流水线加 AI 智能体，逐行给出精准点评。",
        chips=["代码审查", "AI 智能体", "多语言规则", "阿里开源"],
        code_caption="先 clone 仓库，按官方文档配置 LLM 密钥后接入代码评审流程",
    ),
    "cloudflare/security-audit-skill": dict(
        tagline_full="Cloudflare 开源的安全审计智能体技能：六阶段漏洞猎杀",
        tagline_hl="安全审计",
        problem="把编码智能体变成安全审计员，按侦察、猎杀、验证、出报告六阶段挖漏洞，结论可独立核验。",
        chips=["安全审计", "漏洞猎杀", "智能体技能", "Cloudflare"],
        code_caption="clone 后作为技能装入编码智能体，触发多阶段安全审计",
        license_fix="MIT",
    ),
    "addyosmani/agent-skills": dict(
        tagline_full="为 AI 编码智能体准备的 25 套生产级工程技能",
        tagline_hl="工程技能",
        problem="把资深工程师的规范、质量门禁与最佳实践打包成技能，让 AI 智能体全流程稳定按高标准交付。",
        chips=["工程技能", "AI 编码", "质量门禁", "工作流"],
        code_caption="用 npx skills add 安装全部 25 个技能，或 --list 先预览",
    ),
    "Tencent/BrowserSkill": dict(
        tagline_full="腾讯开源：让 AI 智能体借用你已登录的浏览器干活",
        tagline_hl="浏览器",
        problem="解决智能体无法操作真实登录态网页的难题：复用你已登录的浏览器，不干扰手头工作即可自动化。",
        chips=["浏览器自动化", "复用登录态", "腾讯开源", "智能体"],
        code_caption="运行官方脚本一键安装，再把安装目录加入 PATH",
    ),
    "alphaXiv/OpenResearch": dict(
        tagline_full="把编码智能体变成科研智能体：本地优先的研究工作台",
        tagline_hl="科研智能体",
        problem="让编码智能体升级为能读文献、提假设、跑实验、产出成果的科研助手，主打本地优先、数据不出端。",
        chips=["科研智能体", "本地优先", "文献综述", "Rust"],
        code_caption="官方脚本安装后，orx up 拉起本地研究工作台",
    ),
    "anthropics/claude-code": dict(
        tagline_full="Anthropic 出品的终端智能体编码工具 Claude Code",
        tagline_hl="Claude Code",
        problem="常驻终端的 AI 编码智能体：读得懂你的代码库，用自然语言执行日常任务、解释复杂逻辑、跑通 git 流程。",
        chips=["终端编码", "AI 智能体", "代码解释", "git 工作流"],
        code_caption="官方脚本一键安装，终端输入 claude 即可启动",
        license_fix="开源",
    ),
    "NationalSecurityAgency/ghidra": dict(
        tagline_full="NSA 维护的开源软件逆向工程框架 Ghidra",
        tagline_hl="Ghidra",
        problem="提供反汇编、反编译、流程图与脚本化分析等一整套逆向工具，跨 Windows/macOS/Linux 分析各类可执行文件。",
        chips=["逆向工程", "反编译", "NSA 开源", "跨平台"],
        code_caption="解压后进入目录运行，支持 Java/Python 编写扩展脚本",
    ),
    "anthropics/knowledge-work-plugins": dict(
        tagline_full="Anthropic 的知识工作插件库：把 Claude 变成你的岗位专家",
        tagline_hl="知识工作",
        problem="为知识工作者提供可定制插件，把 Claude 变成懂你团队工具、术语与流程的专属岗位专家。",
        chips=["知识工作", "Claude 插件", "岗位专家", "可定制"],
        code_caption="先添加插件市场，再 claude plugin install 指定岗位插件",
    ),
    "Tencent/WeKnora": dict(
        tagline_full="腾讯开源的 LLM 知识平台：文档变 RAG、智能体与自维护 Wiki",
        tagline_hl="知识平台",
        problem="把零散文档一键变成可问答的 RAG、自主推理智能体和会自动更新的知识库，省去自建知识中台的麻烦。",
        chips=["知识平台", "RAG", "自主智能体", "腾讯开源"],
        code_caption="clone 后按文档部署，接入 Ollama 或 OpenAI 即可使用",
        license_fix="开源",
    ),
    "abue-ammar/tinycast": dict(
        tagline_full="纯原生 macOS 启动器：热键 + 剪贴板历史，内存不到 100MB",
        tagline_hl="启动器",
        problem="一个极轻量的 macOS 原生启动器，一个热键唤出常用操作与剪贴板历史，常驻内存不到 100MB。",
        chips=["macOS 原生", "启动器", "剪贴板历史", "极轻量"],
        code_caption="clone 后用 Xcode 构建，或下载已发布的 macOS dmg",
        license_fix="AGPL-3.0",
    ),
}

by_full = {f'{r["owner"]}/{r["repo"]}': r for r in data["repos"]}
for full, u in updates.items():
    r = by_full[full]
    r["tagline_full"] = u["tagline_full"]
    r["tagline_hl"] = u["tagline_hl"]
    r["problem"] = u["problem"]
    r["chips"] = u["chips"]
    r["code_caption"] = u["code_caption"]
    if "license_fix" in u:
        lic = u["license_fix"]
        r["author_note"] = f"{lic} 开源" if lic not in ("开源",) else "开源"
        for s in r["stats"]:
            if s["k"] == "协议":
                s["v"] = lic

f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("已中文化写回", len(updates), "个仓库")
# 校验 hl 是 full 的连续子串
bad = [f for f, r in by_full.items() if r["tagline_hl"] and r["tagline_hl"] not in r["tagline_full"]]
print("hl 校验失败:", bad if bad else "无")
