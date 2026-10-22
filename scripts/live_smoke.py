"""One-time production browser smoke test; public URL and built-in demo only."""
from __future__ import annotations

import csv
from io import StringIO
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = os.getenv("RESEARCHFLOW_LIVE_URL", "https://researchflow-portfolio-msr4p7iwappfodx5am4eshb.streamlit.app/")
OUT = Path("smoke-artifacts")
OUT.mkdir(exist_ok=True)


def main():
    result = {"url": URL, "checks": {}, "notes": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))
        try:
            response = page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            result["http_status"] = response.status if response else None
            app_frame = None
            for _ in range(20):
                for candidate in page.frames:
                    try:
                        if candidate.get_by_role("button", name="情報収集を実行").count():
                            app_frame = candidate
                            break
                    except Exception:
                        pass
                if app_frame is not None:
                    break
                page.mouse.wheel(0, 850)
                page.wait_for_timeout(1000)
            if app_frame is None:
                for candidate in page.frames:
                    try:
                        print("FRAME", candidate.url, "TEXT", repr(candidate.locator("body").inner_text(timeout=3000)[-600:]))
                    except Exception as err:
                        print("FRAME ERROR", candidate.url, str(err)[:220])
                raise AssertionError("Streamlit action button not found in any frame after scrolling")
            print("APP FRAME", app_frame.url)
            result["checks"]["app_rendered"] = "PASS"
            page.screenshot(path=str(OUT / "app.png"), full_page=True)

            app_frame.get_by_role("button", name="情報収集を実行").click()
            app_frame.get_by_role("heading", name="収集・分類結果").wait_for(timeout=90000)
            result["checks"]["local_sample_pipeline"] = "PASS"
            page.screenshot(path=str(OUT / "result.png"), full_page=True)

            with page.expect_download(timeout=30000) as download:
                app_frame.get_by_role("button", name="修正結果をCSVで保存").click()
            output = OUT / "sample.csv"
            download.value.save_as(output)
            rows = list(csv.DictReader(StringIO(output.read_bytes().decode("utf-8-sig"))))
            if len(rows) != 6:
                raise AssertionError(f"Expected six rows, got {len(rows)}")
            if "カテゴリ" not in rows[0] or "参照URL" not in rows[0]:
                raise AssertionError("CSV lacks required columns")
            result["checks"]["csv_download"] = "PASS"
            result["csv_rows"] = len(rows)

            # Diagnostic: external sites may prohibit bots via robots.txt or 403.
            try:
                app_frame.get_by_text("公開URLを取得", exact=True).first.click(timeout=12000)
                area = app_frame.get_by_role("textbox", name="調査したいページのURL（1行に1件、最大8件）")
                area.wait_for(timeout=15000)
                area.fill("https://example.com/")
                area.press("Tab")
                # Streamlit text areas commit to session state on blur/rerun.
                app_frame.get_by_text("処理対象：1件", exact=False).wait_for(timeout=25000)
                from playwright.sync_api import expect
                submit = app_frame.get_by_role("button", name="情報収集を実行")
                expect(submit).to_be_enabled(timeout=20000)
                submit.click(timeout=20000)
                # The prior sample result remains visible while the URL request
                # is running, so wait for evidence of the *new* result.
                app_frame.wait_for_function(
                    """() => {
                        const t = document.body.innerText;
                        return t.includes('Example Domain') ||
                               t.includes('取得できたページはありません') ||
                               t.includes('取得できなかった項目・重複');
                    }""",
                    timeout=60000,
                )
                page.screenshot(path=str(OUT / "url-result.png"), full_page=True)
                body = app_frame.locator("body").inner_text(timeout=10000)
                if "Example Domain" in body:
                    result["checks"]["external_url_fetch"] = "PASS"
                else:
                    result["checks"]["external_url_fetch"] = "UNVERIFIED"
                    result["notes"].append(body[max(0, body.find("収集・分類結果")):][:1800])
            except Exception as exc:
                result["checks"]["external_url_fetch"] = "UNVERIFIED"
                result["notes"].append(f"URL probe: {type(exc).__name__}: {str(exc)[:400]}")
                try:
                    page.screenshot(path=str(OUT / "url-diagnostic.png"), full_page=True, timeout=15000)
                    visible = app_frame.locator("body").inner_text(timeout=5000)
                    idx = visible.find("RESULT / RESEARCH SHEET")
                    result["notes"].append("RESULT_SECTION: " + visible[max(0, idx):][:2700])
                except Exception as diag:
                    result["notes"].append(f"diagnostic capture failed: {diag}")
        except Exception as exc:
            result["failure"] = f"{type(exc).__name__}: {exc}"
            try:
                page.screenshot(path=str(OUT / "failure.png"), full_page=True, timeout=15000)
                result["notes"].append(app_frame.locator("body").inner_text(timeout=5000)[-900:])
            except Exception:
                pass
        finally:
            result["page_errors"] = page_errors[:8]
            browser.close()
            (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False, indent=2))
    mandatory = ("app_rendered", "local_sample_pipeline", "csv_download")
    if any(result["checks"].get(k) != "PASS" for k in mandatory):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
