"""Browser end-to-end test against the real Member 4 FastAPI backend.
Run: python tests/e2e.py while both local servers are running.
Requires Python playwright and Chromium (see README).
"""
from playwright.sync_api import sync_playwright
import json, pathlib, os
BASE='http://127.0.0.1:5173'
ROOT=pathlib.Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,**({'executable_path': os.environ['BROWSER_EXECUTABLE']} if os.environ.get('BROWSER_EXECUTABLE') else {}))
    page=browser.new_page(viewport={'width':1600,'height':1050},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(BASE,wait_until='networkidle',timeout=45000)
    page.locator('.case-item').first.wait_for(timeout=15000)
    print('main title:',page.title())
    print('status:',page.locator('#connection-text').inner_text())
    print('stats:',[page.locator('#stat-'+k).inner_text() for k in ['transactions','alerts','cases']])
    print('case:',page.locator('#selected-case-title').inner_text())
    print('graph edges:',page.locator('.network-edge').count())
    print('timeline:',page.locator('.timeline-row').count())
    page.screenshot(path=str(ROOT/'reports/frontend_desktop.png'),full_page=True)
    assert page.locator('#stat-transactions').inner_text()=='1,20,558' or page.locator('#stat-transactions').inner_text()=='120,558'
    assert page.locator('.network-edge').count()==25
    page.locator('.network-node').first.click()
    print('account filter:',page.locator('#focus-description').inner_text())
    assert 'account' in page.locator('#focus-description').inner_text()
    page.locator('#clear-focus').click()
    page.locator('.network-edge').first.click(force=True)
    print('selected evidence?',page.locator('.evidence-highlight').count())
    assert page.locator('.evidence-highlight').count()==1
    page.locator('#tab-stress').click()
    first_transaction=page.locator('#stress-transaction option').first.get_attribute('value')
    page.locator('#stress-transaction').select_option(first_transaction)
    before=page.locator('#priority-score').inner_text()
    page.locator('#run-stress').click()
    page.locator('.stress-summary').wait_for(timeout=15000)
    print('stress before/after:',page.locator('.stress-score').all_inner_texts())
    scores=page.locator('.stress-score').all_inner_texts()
    assert scores[0]==before
    assert len(scores)==2
    page.screenshot(path=str(ROOT/'reports/frontend_stress_test.png'),full_page=True)
    page.locator('#reset-stress').click()
    assert page.locator('.stress-summary').count()==0
    page.locator('#tab-factors').click()
    assert page.locator('.factor').count()==4
    page.locator('#detector').select_option('temporal_cycle')
    page.wait_for_timeout(750)
    print('filtered count:',page.locator('#queue-total').inner_text())
    page.locator('#detector').select_option('')
    page.locator('#search').fill('NO_CASE_MATCH_XYZ')
    page.wait_for_timeout(1000)
    assert page.locator('.case-item').count()==0
    page.locator('#search').fill('')
    page.wait_for_timeout(750)
    page.locator('#open-dataset').click()
    assert page.locator('#dataset-modal').is_visible()
    page.locator('#close-dataset').click()
    assert not page.locator('#dataset-modal').is_visible()
    assert not errors,errors
    print('PASS: desktop case queue, real network, selection, factors, stress test, filters and dataset dialog')
    mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
    mobile.goto(BASE,wait_until='networkidle',timeout=45000)
    mobile.locator('.case-item').first.wait_for(timeout=15000)
    mobile.screenshot(path=str(ROOT/'reports/frontend_mobile.png'),full_page=True)
    print('mobile page:',mobile.locator('#selected-case-title').inner_text())
    browser.close()
