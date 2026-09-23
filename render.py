#!/usr/bin/env python3
# render.py — 用 Playwright 把系列 HTML 的 .page 截图成 PNG
# 用法: python render.py <in.html> <out_dir>
import os, sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    in_html = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "output", "2026-08-09", "png")
    os.makedirs(out_dir, exist_ok=True)
    # 默认用系统 Google Chrome（Mac 本机已装）；部署到服务器时用 RENDER_CHROME_CHANNEL="" 切到 Playwright 自带 chromium。
    # 若 channel 启动失败（如服务器无系统 Chrome），自动回退 Playwright 自带 chromium，避免硬崩。
    channel = os.environ.get("RENDER_CHROME_CHANNEL", "chrome")
    with sync_playwright() as p:
        browser = None
        if channel:
            try:
                browser = p.chromium.launch(headless=True, channel=channel)
            except Exception as e:
                print(f"[render] channel={channel!r} 启动失败（{e}），回退 Playwright 自带 chromium")
                browser = None
        if browser is None:
            browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 800, "height": 1100}, device_scale_factor=2)
        page.goto("file://" + os.path.abspath(in_html))
        els = page.query_selector_all(".page")
        for i, el in enumerate(els):
            name = f"{i:02d}.png"
            el.screenshot(path=os.path.join(out_dir, name))
            print("rendered", name)
        browser.close()
    print(f"done: {len(els)} pages -> {out_dir}")


if __name__ == "__main__":
    main()
