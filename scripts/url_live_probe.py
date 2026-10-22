"""End-to-end real public URL fetch via deployed ResearchFlow."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

URL=os.environ.get("RESEARCHFLOW_LIVE_URL","https://researchflow-portfolio-msr4p7iwappfodx5am4eshb.streamlit.app/")
TARGET="https://example.com/"
OUT=Path("url-probe-artifacts")
OUT.mkdir(exist_ok=True)

def main():
    out={"app_url":URL,"target_url":TARGET,"checks":{}}
    with sync_playwright() as p:
        browser=p.chromium.launch(channel="chrome",headless=True)
        page=browser.new_page(viewport={"width":1440,"height":900},accept_downloads=True)
        try:
            response=page.goto(URL,wait_until="domcontentloaded",timeout=60000)
            out["http_status"]=response.status if response else None
            frame=None
            for i in range(50):
                for f in page.frames:
                    if f.get_by_role("button",name="情報収集を実行").count():
                        frame=f
                        break
                if frame: break
                page.mouse.wheel(0,750)
                page.wait_for_timeout(1000)
            if frame is None: raise AssertionError("Streamlit input form not found")
            out["checks"]["form"]="PASS"
            frame.get_by_text("公開URLを取得",exact=True).first.click()
            area=frame.get_by_role("textbox",name="調査したいページのURL（1行に1件、最大8件）")
            area.fill(TARGET)
            area.press("Tab")
            frame.get_by_text("処理対象：1件",exact=False).wait_for(timeout=25000)
            button=frame.get_by_role("button",name="情報収集を実行")
            expect(button).to_be_enabled(timeout=15000)
            out["checks"]["url_input"]="PASS"
            page.screenshot(path=str(OUT/"before-run.png"),full_page=True)
            button.click()
            frame.get_by_role("heading",name="収集・分類結果").wait_for(timeout=80000)
            page.screenshot(path=str(OUT/"after-run.png"),full_page=True)
            body=frame.locator("body").inner_text(timeout=6000)
            idx=body.find("RESULT / RESEARCH SHEET")
            out["result_text"]=body[max(0,idx):max(0,idx)+2500]
            # Streamlit data_editor cells are not exposed as normal body text.
            # Validate the exported record rather than a brittle DOM substring.
            import csv
            with page.expect_download(timeout=30000) as download:
                frame.get_by_role("button",name="修正結果をCSVで保存").click()
            dest=OUT/"real-url-result.csv"
            download.value.save_as(dest)
            with dest.open(encoding="utf-8-sig",newline="") as fp:
                rows=list(csv.DictReader(fp))
            out["csv_rows"]=rows
            if len(rows)!=1:
                raise AssertionError(f"Expected one real URL row, got {len(rows)}")
            if rows[0].get("参照URL")!=TARGET:
                raise AssertionError(f"CSV URL mismatch: {rows[0].get('参照URL')}")
            if "Example Domain" not in rows[0].get("ページタイトル",""):
                raise AssertionError(f"HTML title extraction mismatch: {rows[0].get('ページタイトル')}")
            if rows[0].get("入力元")!="公開URL":
                raise AssertionError("CSV row came from a sample, not a fetched public URL")
            out["checks"]["real_url_extract"]="PASS"
            out["checks"]["real_url_csv"]="PASS"
        except Exception as exc:
            out["error"]=type(exc).__name__+": "+str(exc)[:500]
            try:
                page.screenshot(path=str(OUT/"error.png"),full_page=True,timeout=15000)
                out["frame_texts"]=[]
                for f in page.frames:
                    try:out["frame_texts"].append({"url":f.url,"text":f.locator("body").inner_text(timeout=3000)[-2400:]})
                    except Exception:pass
            except Exception:pass
        finally:
            (OUT/"result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
            print(json.dumps(out,ensure_ascii=False,indent=2),flush=True)
            browser.close()
    if out["checks"].get("real_url_csv")!="PASS":raise SystemExit(1)

if __name__=="__main__":main()
