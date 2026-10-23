"""Verify actual company sites through the deployed public Streamlit app.

Uses ONLY public pages and the existing URL-input UI. Saves the unmodified
exported CSV, page screenshot, and a structured quality/limitations report.
A fetch rejection remains a failure/blocked observation, never a fake success.
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlparse

from playwright.sync_api import expect, sync_playwright

APP_URL = os.getenv("RESEARCHFLOW_LIVE_URL", "https://researchflow-portfolio-msr4p7iwappfodx5am4eshb.streamlit.app/")
PAGES = [
    {"company": "ARTVIBES", "url": "https://artvibes.co.jp/company/", "identity_terms": ["アートバイブス", "artvibes"], "expected_category": "企業・団体"},
    {"company": "サイボウズ", "url": "https://cybozu.co.jp/company/outline/", "identity_terms": ["サイボウズ", "cybozu"], "expected_category": "企業・団体"},
    {"company": "さくらインターネット", "url": "https://www.sakura.ad.jp/corporate/corp/profile/", "identity_terms": ["さくらインターネット", "sakura"], "expected_category": "企業・団体"},
    {"company": "はてな", "url": "https://www.hatena.ne.jp/ownedmedia/company", "identity_terms": ["はてな", "hatena"], "expected_category": "企業・団体"},
    {"company": "ARTVIBESトップページ", "url": "https://artvibes.co.jp/", "identity_terms": ["アートバイブス", "artvibes"], "expected_category": "商品・サービス"},
]
OUT = Path("corporate-test-results")
OUT.mkdir(exist_ok=True)


def normalized(t):
    return unicodedata.normalize("NFKC", str(t)).casefold()


def capture_result():
    report = {
        "app": APP_URL,
        "target_urls": [x["url"] for x in PAGES],
        "inputs": PAGES,
        "checks": {},
        "rows": [],
        "per_site": [],
        "notes": [],
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 920}, accept_downloads=True)
        try:
            response = page.goto(APP_URL, wait_until="domcontentloaded", timeout=65000)
            report["app_status"] = response.status if response else None

            frame = None
            for _ in range(65):
                for f in page.frames:
                    try:
                        if f.get_by_role("button", name="情報収集を実行").count():
                            frame = f
                            break
                    except Exception:
                        pass
                if frame:
                    break
                page.mouse.wheel(0, 820)
                page.wait_for_timeout(700)
            if frame is None:
                raise AssertionError("The deployed Streamlit input form could not be found")
            report["checks"]["live_app_loaded"] = True
            version_text = frame.locator("body").inner_text(timeout=9000)
            report["checks"]["new_classification_ui"] = "8カテゴリに分類" in version_text
            if not report["checks"]["new_classification_ui"]:
                raise AssertionError("Published app is not yet using the new eight-category classifier")
            frame.get_by_text("公開URLを取得", exact=True).first.click(timeout=18000)
            area = frame.get_by_role("textbox", name="調査したいページのURL（1行に1件、最大8件）")
            area.fill("\n".join(x["url"] for x in PAGES))
            area.press("Tab")
            frame.get_by_text(f"処理対象：{len(PAGES)}件", exact=False).wait_for(timeout=25000)
            button = frame.get_by_role("button", name="情報収集を実行")
            expect(button).to_be_enabled(timeout=20000)
            report["checks"]["all_real_urls_accepted"] = True
            page.screenshot(path=str(OUT / "before-run.png"), full_page=True)
            button.click(timeout=25000)
            frame.get_by_role("heading", name="収集・分類結果").wait_for(timeout=180000)
            report["checks"]["result_panel_visible"] = True
            # Streamlit progressively renders the results after a rerun. An
            # existing heading can become visible before metrics/editor/download.
            frame.get_by_role("button", name="修正結果をCSVで保存").wait_for(
                state="visible", timeout=130000
            )
            report["checks"]["results_ready"] = True
            page.screenshot(path=str(OUT / "after-run.png"), full_page=True)

            content = frame.locator("body").inner_text(timeout=9000)
            i = content.find("RESULT / RESEARCH SHEET")
            report["result_panel_text"] = content[i:i+4000] if i>=0 else content[-4000:]
            try:
                button = frame.get_by_role("button", name="修正結果をCSVで保存")
                if button.count():
                    with page.expect_download(timeout=35000) as download:
                        button.click(timeout=20000)
                    download.value.save_as(OUT / "corporate-export.csv")
                    with (OUT / "corporate-export.csv").open(encoding="utf-8-sig", newline="") as fp:
                        rows = list(csv.DictReader(fp))
                    report["rows"] = rows
                    report["checks"]["csv_export_downloaded"] = True
                else:
                    report["checks"]["csv_export_downloaded"] = False
            except Exception as exc:
                report["notes"].append(f"CSV download problem: {type(exc).__name__}: {str(exc)[:400]}")

            seen = set()
            for site in PAGES:
                entry = {"company": site["company"], "input_url": site["url"], "status": "NOT_EXPORTED"}
                matches = [r for r in report["rows"] if r.get("参照URL", "").rstrip("/") == site["url"].rstrip("/")]
                if matches:
                    row = matches[0]
                    title = row.get("ページタイトル", "")
                    desc = row.get("概要", "")
                    source = row.get("入力元", "")
                    identity = any(term in normalized(title + " " + desc) for term in [normalized(t) for t in site["identity_terms"]])
                    entry.update({
                        "status": "EXPORTED",
                        "actual_url": row.get("参照URL", ""),
                        "title": title,
                        "summary": desc,
                        "category": row.get("カテゴリ"),
                        "expected_category": site["expected_category"],
                        "page_purpose_matches": row.get("カテゴリ") == site["expected_category"],
                        "classification_method": row.get("分類方法"),
                        "classification_reason": row.get("分類根拠"),
                        "input_source": source,
                        "is_partial": "部分取得" in source,
                        "identity_in_title_or_summary": identity,
                        "has_meaningful_summary": len(desc) > 20 and desc != "（概要なし）",
                        "title_is_not_placeholder": len(title.strip()) >= 4 and "タイトルなし" not in title,
                    })
                    seen.add(site["url"])
                report["per_site"].append(entry)

            report["checks"]["row_count"] = len(report["rows"])
            report["checks"]["exported_urls_expected"] = all(
                r.get("参照URL") in [x["url"] for x in PAGES] for r in report["rows"]
            )
            report["checks"]["no_sample_rows"] = all(
                r.get("入力元") in ("公開URL", "公開URL（部分取得）")
                for r in report["rows"]
            )
            report["checks"]["real_company_rows"] = sum(1 for x in report["per_site"] if x["status"] == "EXPORTED")
            report["checks"]["correct_purpose_categories"] = sum(
                1 for x in report["per_site"] if x.get("page_purpose_matches")
            )
            report["checks"]["obsolete_fields_absent"] = (
                len(report["rows"]) == len(PAGES)
                and all("所在地" not in r and "開催日" not in r for r in report["rows"])
            )
            report["checks"]["all_rows_have_explanations"] = (
                len(report["rows"]) == len(PAGES)
                and all(r.get("分類根拠") for r in report["rows"])
            )
            report["checks"]["identified_company_rows"] = sum(
                1 for x in report["per_site"] if x.get("identity_in_title_or_summary")
            )
        except Exception as exc:
            report["fatal_error"] = f"{type(exc).__name__}: {str(exc)[:1200]}"
            try:
                page.screenshot(path=str(OUT / "error.png"), full_page=True, timeout=15000)
                report["browser_frames"] = [
                    {"url": f.url, "text_tail": f.locator("body").inner_text(timeout=5000)[-2000:]}
                    for f in page.frames
                ]
            except Exception:
                pass
        finally:
            (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print("CORPORATE_CHECK_REPORT")
            print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
            browser.close()
    # The test's job is to expose the true behavior, including partial failures.
    # A majority of real corporate sites must be exportable, otherwise fail CI.
    ok = (report["checks"].get("real_company_rows", 0) >= 3
          and report["checks"].get("exported_urls_expected") is True
          and report["checks"].get("no_sample_rows") is True
          and report["checks"].get("new_classification_ui") is True
          and report["checks"].get("correct_purpose_categories", 0) == len(PAGES)
          and report["checks"].get("all_rows_have_explanations") is True
          and report["checks"].get("obsolete_fields_absent") is True)
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    capture_result()
