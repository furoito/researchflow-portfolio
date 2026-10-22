from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'preview.html').read_text(encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox'])
    for width,height,name in [(1440,900,'desktop'),(390,844,'mobile'),(320,750,'small')]:
        page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1,accept_downloads=True)
        errs=[]
        page.on('pageerror',lambda e:errs.append(str(e)))
        page.set_content(HTML,wait_until='load')
        page.locator('#html-import').set_input_files([str(ROOT/'samples/01_bakery.html'),str(ROOT/'samples/03_observatory.html')])
        page.wait_for_function("document.querySelector('#input-count').textContent==='2'")
        assert page.locator('#items tr').count()==2
        assert page.locator('#file-status').inner_text().find('成功 2件')>=0
        assert page.locator('#items tr .rf-category-edit').count()==2
        page.locator('#items tr').first.locator('.rf-status-edit').select_option('確認済み')
        page.locator('#items tr').nth(1).locator('.rf-status-edit').select_option('対象外')
        with page.expect_download() as dl:
            page.locator('.rf-download').click()
        target=ROOT/'assets'/(f'dynamic_export_{name}.csv')
        dl.value.save_as(target)
        exported=target.read_bytes().decode('utf-8-sig')
        assert '確認済み' in exported and '対象外' not in exported and '参照URL' in exported
        assert len(exported.splitlines())==2,exported
        scroll=page.evaluate('({s:document.documentElement.scrollWidth,w:document.documentElement.clientWidth})')
        assert scroll['s']<=scroll['w']+1,scroll
        page.screenshot(path=str(ROOT/'assets'/(f'live_preview_{name}.png')),full_page=True)
        page.locator('#reset-demo').click()
        assert page.locator('#items tr').count()==6
        assert page.locator('#input-count').inner_text()=='6'
        assert not errs,errs
        print(name,'OK uploaded/edited/exported/reset',scroll)
        page.close()
    browser.close()
