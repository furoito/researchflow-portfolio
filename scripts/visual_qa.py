"""Verify offline preview in desktop/mobile Chromium; does not launch Streamlit."""
from __future__ import annotations

import base64
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGE_HTML = (ROOT / "preview.html").read_text(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, executable_path="/usr/bin/chromium", args=["--no-sandbox"])
    for label,width,height in [("desktop",1440,900),("mobile",390,844)]:
        page = browser.new_page(viewport={"width":width,"height":height}, device_scale_factor=1)
        errors=[]
        page.on("pageerror",lambda err: errors.append(str(err)))
        page.set_content(PAGE_HTML, wait_until="load")
        page.screenshot(path=str(ROOT / "assets" / ("preview.png" if label=="desktop" else "preview_mobile.png")),full_page=True)
        page.screenshot(path=str(ROOT / "assets" / ("preview_hero.png" if label=="desktop" else "preview_mobile_first.png")))
        if label == "desktop":
            page.locator("#demo").screenshot(path=str(ROOT / "assets" / "preview_results.png"))
        overhang=page.evaluate('({scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth})')
        assert overhang["scrollWidth"] <= overhang["clientWidth"] + 1, f"Horizontal overflow {label}: {overhang}"
        assert page.locator('#items tr:visible').count()==6
        page.locator('.rf-action-primary').click()
        page.wait_for_function("Math.abs(document.querySelector('#demo').getBoundingClientRect().top) < innerHeight / 2", timeout=5000)
        assert page.evaluate('window.location.hash') == '#demo'
        target_top=page.evaluate('document.querySelector("#demo").getBoundingClientRect().top')
        assert abs(target_top) < height/2, f"CTA misses destination in {label}: {target_top}"
        page.select_option('#category','観光')
        assert page.locator('#items tr:visible').count()==2
        page.select_option('#category','all')
        page.fill('#search','資料館')
        assert page.locator('#items tr:visible').count()==1
        page.fill('#search','無い名称123')
        assert page.locator('#items tr:visible').count()==0
        assert page.locator('#empty').is_visible()
        page.fill('#search','')
        assert page.locator('#items tr:visible').count()==6
        href=page.locator('.rf-download').get_attribute('href')
        assert href.startswith('data:text/csv;base64,')
        extracted=base64.b64decode(href.split(',',1)[1])
        expected=(ROOT/'assets/sample_results.csv').read_bytes()
        assert extracted==expected
        assert not errors,errors
        print(label, 'OK: CTA, filters, empty state, CSV, overflow, errors',overhang)
        page.close()
    browser.close()
