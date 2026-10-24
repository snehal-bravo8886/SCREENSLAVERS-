"""Rendered-browser test with real Backend 4 API data.

The hardened CI browser blocks all network URLs by administrator policy. We load
our real HTML/CSS/JS into about:blank, and bridge window.fetch through Python
urllib to the unmodified local backend. This verifies DOM interactions and
backend response handling but does NOT validate actual browser CORS/network.
"""
import pathlib, re, json, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
BACKEND='http://127.0.0.1:8000'
def api_bridge(source,url,method,body):
    if not url.startswith(BACKEND+'/'):
        raise ValueError('Unexpected URL '+url)
    req=urllib.request.Request(url,data=body.encode() if body and method!='GET' else None,
        headers={'Content-Type':'application/json'} if method!='GET' else {},method=method)
    try:
        with urllib.request.urlopen(req,timeout=10) as resp:
            content=resp.read().decode();status=resp.status
    except urllib.error.HTTPError as exc:
        content=exc.read().decode();status=exc.code
    return {'status':status,'body':json.loads(content)}

def read_bundle():
    result=[]
    for name in ('format','graph','api','app'):
        content=(ROOT/'js'/f'{name}.js').read_text()
        content=re.sub(r'^import\s+.+?\s+from\s+[^;]+;\s*$', '', content, flags=re.M)
        content=re.sub(r'\bexport\s+(?=const|class|function)', '', content)
        result.append('// SOURCE: '+name+'\n'+('const h=escapeHTML;\n' if name=='app' else '')+content)
    return '\n'.join(result)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1600,'height':980},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda err:errors.append(str(err)))
    page.expose_binding('__apiBridge',api_bridge)
    html=(ROOT/'index.html').read_text()
    html=re.sub(r'<script\s+type="module"[^>]+></script>', '', html)
    html=re.sub(r'<link\s+rel="stylesheet"[^>]+>', '', html)
    page.set_content(html)
    css=(ROOT/'css/app.css').read_text()
    css=css.split('\n',1)[1]  # drop remote font import for offline browser
    page.add_style_tag(content=css)
    page.add_script_tag(content='''
window.fetch = async (url, options={}) => {
  const response=await window.__apiBridge(String(url),options.method||'GET',options.body||'');
  return {ok:response.status>=200&&response.status<300,status:response.status,
    json:async()=>response.body,text:async()=>JSON.stringify(response.body)};
};''')
    page.add_script_tag(content=read_bundle())
    page.locator('.network-edge').first.wait_for(timeout=20000)
    print('backend status:',page.locator('#connection-text').inner_text())
    print('dataset counters:',[page.locator('#stat-'+x).inner_text() for x in ('transactions','alerts','cases')])
    print('case:',page.locator('#selected-case-title').inner_text())
    print('graph:',page.locator('.network-node').count(),'nodes;',page.locator('.network-edge').count(),'edges')
    print('timeline records:',page.locator('.timeline-row').count())
    assert page.locator('#connection-text').inner_text()=='Backend online'
    assert page.locator('#stat-cases').inner_text()=='2,573'
    assert page.locator('.network-edge').count()==25
    assert page.locator('.timeline-row').count()==25
    page.screenshot(path=str(ROOT/'reports/frontend_desktop.png'),full_page=True)
    page.locator('.network-node').first.click()
    assert 'Showing transfers touching account' in page.locator('#focus-description').inner_text()
    page.locator('#clear-focus').click()
    page.locator('.timeline-row').first.click()
    assert page.locator('.evidence-highlight').count()==1
    page.locator('#tab-factors').click()
    assert page.locator('.factor').count()==4
    assert page.locator('.score-formula').count()==1
    page.locator('#tab-stress').click()
    first_transaction=page.locator('#stress-transaction option').first.get_attribute('value')
    page.locator('#stress-transaction').select_option(first_transaction)
    before=page.locator('#priority-score').inner_text()
    page.locator('#run-stress').click()
    page.locator('.stress-summary').wait_for(timeout=15000)
    scores=page.locator('.stress-score').all_inner_texts()
    print('stress test:',scores)
    assert scores[0]==before
    assert len(scores)==2
    page.screenshot(path=str(ROOT/'reports/frontend_stress_test.png'),full_page=True)
    page.locator('#reset-stress').click()
    assert page.locator('.stress-summary').count()==0
    page.locator('#detector').select_option('temporal_cycle')
    page.wait_for_timeout(400)
    assert page.locator('#queue-total').inner_text()!='0'
    page.locator('#detector').select_option('')
    page.locator('#search').fill('FAKE_ID_NOT_FOUND')
    page.wait_for_timeout(500)
    assert page.locator('.case-item').count()==0
    page.locator('#search').fill('')
    page.wait_for_timeout(500)
    page.locator('#open-dataset').click()
    assert page.locator('#dataset-modal').is_visible()
    page.locator('#close-dataset').click()
    assert not page.locator('#dataset-modal').is_visible()
    assert not errors,errors
    print('PASS: rendered UI interactions with genuine backend dataset')
    mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
    mobile_errors=[]
    mobile.on('pageerror',lambda err:mobile_errors.append(str(err)))
    mobile.expose_binding('__apiBridge',api_bridge)
    mobile.set_content(html)
    mobile.add_style_tag(content=css)
    mobile.add_script_tag(content='''window.fetch=async (url,options={})=>{const r=await window.__apiBridge(String(url),options.method||'GET',options.body||'');return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>r.body,text:async()=>JSON.stringify(r.body)}};''')
    mobile.add_script_tag(content=read_bundle())
    mobile.locator('.network-edge').first.wait_for(timeout=20000)
    mobile.screenshot(path=str(ROOT/'reports/frontend_mobile.png'),full_page=True)
    assert not mobile_errors,mobile_errors
    print('PASS: mobile layout rendered')
    browser.close()
