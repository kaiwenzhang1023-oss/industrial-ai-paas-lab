from pathlib import Path
import json
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
assets=ROOT/'enterprise_workbench/site'
html=(assets/'index.html').read_text(encoding='utf-8')
html=html.replace('<script src="./', '<script data-skip-src="./')
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1365,'height':850})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.set_content(html)
 manufacturing=(assets/'data/manufacturing.json').read_text(encoding='utf-8')
 page.evaluate('''async json => { window.fetch=async (url, opts={})=>{ const u=String(url); let obj;
 if(u.includes('manufacturing.json')) obj=JSON.parse(json);
 else if(u==='/ready') obj={status:'ready'};
 else if(u.includes('/capabilities')) obj={production_ready:false};
 else if(u.includes('/preview/session')) obj={access_token:'fake-token',tenant:'guest-123',role:'admin'};
 else if(u.includes('/enterprise/me')) obj={tenant:'guest-123',role:'admin',actor:'visitor'};
 else obj={detail:'NO_PG_IN_BROWSER_MOCK'};
 return new Response(JSON.stringify(obj),{status:200,headers:{'content-type':'application/json'}});
 };}''', manufacturing)
 for asset in ['engine.js','decision.js','decision-evidence.js','decision-reasoning.js','closure.js','portable.js','app.js','onboarding.js','enterprise-status.js']:
  page.add_script_tag(content=(assets/asset).read_text(encoding='utf-8'))
 page.wait_for_selector('#vbEnterpriseTab',timeout=12000)
 assert page.locator('#vbEnterpriseTab').count()==1
 page.locator('#vbEnterpriseTab').click()
 assert page.locator('#vbEnterprisePage').is_visible()
 assert page.locator('#rc2Pane').is_visible()
 assert not page.locator('#body').is_visible()
 page.locator('#rc2Connect').click()
 page.wait_for_function('document.querySelector("#rc2Who").textContent.includes("guest-")',timeout=10000)
 assert page.locator('#rc2Mrp').is_enabled()
 print('BROWSER_NAV_TAB=PASS; ENTERPRISE_PANE=PASS; SESSION=PASS; ROLE_CONTROL=PASS')
 page.locator('[data-tab="orders"]').click()
 assert not page.locator('#vbEnterprisePage').is_visible()
 assert page.locator('#body').is_visible()
 print('BROWSER_RETURN_STATIC_SIMULATION=PASS')
 print('PAGE_ERRORS',errors)
 assert not errors,errors
 browser.close()
