#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-08-16 Top3 叙事精修：覆盖自动生成的英文占位内容。"""
import json
import pathlib

BASE = pathlib.Path(__file__).parent
DATA = BASE / "data_2026-08-16.json"

REFINE = {
    "cordiverse/cordis": {
        "author_note": "MIT 开源",
        "tagline_full": "插件拔掉那一刻，副作用自己收干净",
        "tagline_hl": "副作用自己收干净",
        "problem": (
            "长跑的 Node 服务最怕热插拔：一个模块卸载了，它当初注册的事件监听、定时器、"
            "对外服务却还赖在内存里，重启才能真正清干净。cordis 把「谁注册的副作用谁负责回收」"
            "写进了框架内核——插件函数返回什么，就是它的卸载逻辑；ctx.effect() 登记的副作用由 "
            "fiber 生命周期统一托管，配上 HMR 插件就能改完代码即时生效，不用重启进程。"
        ),
        "chips": [
            {"t": "插件卸载自动回收副作用", "w": True},
            {"t": "Context 依赖注入 + 服务隔离", "w": True},
            "fiber 管生命周期",
            "HMR 热模块替换",
            "TypeScript 类型完备",
            "9 个内建包按需取用",
        ],
        "code": [
            [["cm", "# 核心包就叫 cordis（v4 尚在 rc）"]],
            [["", "npm install cordis"]],
            [["", ""]],
            [["cm", "// 插件 = 一个函数，返回值即卸载逻辑"]],
            [["", "import { Context } from 'cordis'"]],
            [["", "const root = new Context()"]],
            [["", ""]],
            [["", "await root.plugin((ctx, config) => {"]],
            [["", "  ctx.on('data', handler)      "], ["cm", "// 注册的副作用"]],
            [["", "  return () => cleanup()       "], ["cm", "// 卸载时自动执行"]],
            [["", "}, { foo: 'bar' })"]],
        ],
        "code_caption": "配 @cordisjs/plugin-hmr 可改完即生效 · API 尚未稳定，尝鲜锁版本",
    },
    "cathrynlavery/diagram-design": {
        "author_note": "MIT 开源",
        "tagline_full": "让 AI 画出设计师不想吐槽的配图",
        "tagline_hl": "设计师不想吐槽",
        "problem": (
            "写文章要配架构图，让 AI 画就得到一堆圆角灰盒子，跟自己站点风格完全不搭；"
            "不想认命就得在 Figma 里磨半小时。作者干脆做成一个 Claude Code / Codex / Pi 技能包："
            "近 30 种编辑级图表类型，读你的网站自动对齐品牌色，产出自带审美的静态 HTML + SVG，"
            "浏览器直接打开，没有构建步骤也不依赖外部图片。"
        ),
        "chips": [
            {"t": "近 30 种编辑级图表", "w": True},
            {"t": "纯静态 HTML+SVG", "w": True},
            "无 Figma / 无构建步骤",
            "明暗 + 全编辑三套变体",
            "可重绘 draw.io / Mermaid",
            "语义模式与布局解耦",
        ],
        "code": [
            [["cm", "# Claude Code：加市场源后装插件"]],
            [["", "/plugin marketplace add cathrynlavery/diagram-design"]],
            [["", "/plugin install diagram-design@diagram-design"]],
            [["", ""]],
            [["cm", "# Codex 同款两行"]],
            [["", "codex plugin marketplace add cathrynlavery/diagram-design"]],
            [["", "codex plugin add diagram-design@diagram-design"]],
        ],
        "code_caption": "装完直接让 AI「画张架构图」· 输出可浏览器直开，无需 JS",
    },
    "cursor/plugins": {
        "author_note": "MIT 开源",
        "tagline_full": "Cursor 把官方插件的做法整个摊开给你看",
        "tagline_hl": "整个摊开给你看",
        "problem": (
            "想给编辑器里的 AI 加点自家规矩，最难的不是写提示词，而是不知道一个「插件」到底该长什么样。"
            "Cursor 直接把官方插件市场开源了：每个插件一个目录，manifest、技能、规则、MCP 服务端定义各归各位。"
            "从 PR 深度审计、并行云端 agent 编排，到 Gmail / Drive / Salesforce 这类远程 MCP 接入，"
            "都是能照着抄的现成样例。"
        ),
        "chips": [
            {"t": "官方插件规范 + 全部源码", "w": True},
            {"t": "20+ 现成插件可抄", "w": True},
            "skills / rules / mcp.json 三件套",
            "marketplace.json 聚合清单",
            "含第三方远程 MCP 接入",
            "create-plugin 脚手架",
        ],
        "code": [
            [["cm", "# 一个插件目录长这样（照着建即可）"]],
            [["", "plugin-name/"]],
            [["", "├── .cursor-plugin/plugin.json  "], ["cm", "# 插件清单"]],
            [["", "├── skills/                     "], ["cm", "# SKILL.md 带 frontmatter"]],
            [["", "├── rules/                      "], ["cm", "# .mdc 规则文件"]],
            [["", "└── mcp.json                    "], ["cm", "# MCP 服务端定义"]],
            [["", ""]],
            [["cm", "# 根目录 marketplace.json 聚合所有插件"]],
        ],
        "code_caption": "先读 create-plugin 与 cursor-team-kit 两个官方样例最省事",
    },
}


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    hit = []
    for r in data["repos"]:
        key = f"{r['owner']}/{r['repo']}"
        if key in REFINE:
            r.update(REFINE[key])
            hit.append(key)
    # 兜底：清掉其余条目 author_note 的 "开源 开源" 重复
    for r in data["repos"]:
        if r.get("author_note") == "开源 开源":
            r["author_note"] = "开源"
        for s in r.get("stats", []):
            if s.get("k") == "协议" and s.get("v") == "开源 开源":
                s["v"] = "开源"
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已精修 {len(hit)} 个：{hit}")
    missing = [k for k in REFINE if k not in hit]
    if missing:
        print(f"警告：未命中 {missing}")


if __name__ == "__main__":
    main()
