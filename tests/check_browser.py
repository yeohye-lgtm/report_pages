"""Responsive/interaction checks against generated HTML; screenshots are CI artifacts."""
import json
import sys
import shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from report_ui import build_html,classify,legacy_view
from test_report import fixture

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test-artifacts';OUT.mkdir(exist_ok=True)
source=ROOT/'public/ai-risk/latest.html'
if not source.exists():
    source=OUT/'fixture.html';source.write_text(build_html(classify(fixture())),encoding='utf-8')
results=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'],executable_path=shutil.which('chromium'))
    for width in (320,360,390,768):
        page=browser.new_page(viewport={'width':width,'height':900},device_scale_factor=1)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(source.read_text(encoding='utf-8'))
        page.wait_for_selector('#panel-today')
        assert page.locator('html').get_attribute('data-layout-revision')=='2.0.0'
        assert page.locator('.axis-row').count()==5
        assert page.locator('.stage[data-active=true]').count()<=1
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'overflow {width}'
        for key in ('funding','demand','borrower','gpu','contagion','method','about','next'):
            page.locator(f'[data-sheet="{key}"]').first.click()
            assert page.locator('#detail-sheet').is_visible(), key
            page.keyboard.press('Escape')
            assert not page.locator('#detail-sheet').is_visible(), key
        for key in ('trend','evidence','today'):
            page.locator('#tab-'+key).click()
            assert page.locator('#panel-'+key).is_visible()
            assert page.locator('[role=tabpanel]:visible').count()==1
        page.locator('#tab-today').focus();page.keyboard.press('ArrowRight')
        assert page.locator('#tab-trend').get_attribute('aria-selected')=='true'
        page.locator('#tab-today').click()
        page.screenshot(path=str(OUT/f'today-{width}.png'),full_page=True)
        page.locator('[data-sheet=funding]').click()
        page.screenshot(path=str(OUT/f'detail-{width}.png'),full_page=False)
        ref=page.locator('#detail-sheet [data-ref]').first
        if ref.count():
            ref.click();assert page.locator('#panel-evidence').is_visible()
            assert page.locator('#sources-details').get_attribute('open') is not None
        else:page.keyboard.press('Escape')
        page.locator('#tab-today').click()
        # Text-only enlargement, not a pixel-density change.
        page.evaluate("""() => {
          const els=[...document.querySelectorAll('body *')].filter(e=>!['SCRIPT','STYLE','SVG','PATH'].includes(e.tagName));
          const sizes=els.map(e=>parseFloat(getComputedStyle(e).fontSize));
          els.forEach((e,i)=>e.style.fontSize=(sizes[i]*2)+'px');
        }""")
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), f'200% overflow {width}'
        page.screenshot(path=str(OUT/f'text-200-{width}.png'),full_page=True)
        assert not errors,errors
        results.append({'width':width,'tabs':'pass','dialogs':'pass','horizontal_overflow':False,'text_200_percent':'pass'})
        page.close()
    browser.close()
(OUT/'browser-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results))
