"""Version B RC3 UI interaction regression with deterministic mocked HTTP contracts.
Real PostgreSQL/cloud acceptance is a separate gate, never asserted by this test.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'enterprise_workbench/site'
OUT=ROOT/'evidence'
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1450,'height':990},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    html=(SITE/'index.html').read_text(encoding='utf-8').replace('<script src="./','<script data-skip-src="./')
    html=html.replace('<link rel="stylesheet" href="./style.css">','').replace('<link rel="stylesheet" href="./enterprise-console.css">','')
    # about:blank is used because automated network navigation is restricted in this runtime.
    page.set_content(html)
    for name in ['style.css','enterprise-console.css']:
        page.add_style_tag(content=(SITE/name).read_text(encoding='utf-8'))
    manufacturing=(SITE/'data/manufacturing.json').read_text(encoding='utf-8')
    mock=r'''async data=>{
      const stats={calls:[],createPayloads:[],state:'WAITING_REVIEW',command:'',decision:null,worker:'PENDING',receipt:null,events:[],runId:'MRP-1234567890abcdef'};
      window.__httpMock=stats;
      window.fetch=async (url,opts={})=>{
        const path=String(url),method=opts.method||'GET'; stats.calls.push([method,path]);
        const payload=opts.body?JSON.parse(opts.body):{};
        const out=(v,s=200)=>new Response(JSON.stringify(v),{status:s,headers:{'content-type':'application/json'}});
        const auth=opts.headers?.Authorization||'';
        if(path.includes('manufacturing.json'))return out(JSON.parse(data));
        if(path==='/ready')return out({status:'ready',database:'postgresql',scope:'preview_only'});
        if(path==='/api/v1/version-b/preview/session')return out({access_token:'mock-session-token',tenant:'guest-test1',expires_in:7200,role:'admin'});
        if(path.includes('/enterprise/')&&auth!=='Bearer mock-session-token')return out({detail:'AUTH_REQUIRED'},401);
        if(path.endsWith('/enterprise/me'))return out({tenant:'guest-test1',role:'admin',actor:'visitor'});
        const run={run_id:stats.runId,input_hash:'e'.repeat(64),rule_version:'MRP-V0.3',status:'COMPLETED',
          snapshot:{as_of:'2026-10-29'},lines:[{material:'BR-01',date:'2026-11-29',gross:'200',net:'80',planned:'80',closing:'0'},
          {material:'EM-100',date:'2026-11-30',gross:'100',net:'100',planned:'100',closing:'0'}],
          pegs:[{material:'BR-01',date:'2026-11-29',order_id:'SO-2026-001',gross:'200',from_stock:'120',from_receipts:'0',from_planned:'80'}]};
        const comm=()=>stats.command?{command_id:stats.command,run_id:stats.runId,decision:'APPROVED',actor:'visitor',status:stats.worker,attempts:stats.worker==='DONE'?1:0,receipt:stats.receipt,last_error:null,external_execution:false}:null;
        const overview=()=>({run_id:stats.runId,tenant:'guest-test1',source:'PERSISTED_POSTGRESQL',snapshot_hash:'e'.repeat(64),workflow:{state:stats.state,version:stats.state==='WAITING_REVIEW'?0:stats.state==='APPROVED_QUEUED'?1:2},plan:{line_count:2,peg_count:1},decision:stats.decision,command:comm(),events:stats.events,external_execution:false});
        if(path.endsWith('/enterprise/mrp/runs')&&method==='POST'){stats.createPayloads.push(payload);stats.state='WAITING_REVIEW';stats.command='';stats.decision=null;stats.worker='PENDING';stats.receipt=null;stats.events=[];return out({run_id:stats.runId,source:'postgresql',lines:2,pegs:1,simulation:false},201);}
        if(path.endsWith('/enterprise/mrp/runs/'+stats.runId))return out({tenant:'guest-test1',run,canonical_snapshot:{as_of:'2026-10-29'},snapshot_hash:'e'.repeat(64),source:'postgresql'});
        // A second run in the same guest tenant: no decision/outbox/receipt yet.
        if(path.endsWith('/enterprise/mrp/runs/MRP-another-run'))return out({tenant:'guest-test1',run:{...run,run_id:'MRP-another-run'},canonical_snapshot:{as_of:'2026-10-29'},snapshot_hash:'e'.repeat(64),source:'postgresql'});
        if(path.endsWith('/enterprise/review/overview/MRP-another-run'))return out({...overview(),run_id:'MRP-another-run',workflow:{state:'WAITING_REVIEW',version:0},decision:null,command:null,events:[]});
        if(path.endsWith('/enterprise/review/overview/'+stats.runId))return out(overview());
        if(path.endsWith('/enterprise/workflows/'+stats.runId))return out({run_id:stats.runId,state:stats.state,version:1,events:stats.events});
        if(path.endsWith('/enterprise/decisions')&&method==='POST'){
          if(stats.state!=='WAITING_REVIEW')return out({detail:'WORKFLOW_NOT_REVIEWABLE'},409);
          stats.decision={type:payload.decision,reason:payload.reason,actor:'visitor',at:'2026-11-04T14:15:00Z'};
          stats.command='00000000-0000-4000-8000-000000000001';stats.state=payload.decision==='APPROVED'?'APPROVED_QUEUED':'REJECTED';
          stats.events.push({action:payload.decision,actor:'visitor',at:'2026-11-04T14:15:00Z',reference:stats.command});
          return out({command_id:stats.command,status:'ACCEPTED',execution_status:'PENDING',external_execution:false},202);
        }
        if(path.endsWith('/enterprise/worker/dispatch')&&method==='POST'){
          stats.worker='DONE';stats.state='EXECUTED_INTERNAL';stats.receipt={status:'VALIDATED_INTERNAL',checked_at:'2026-11-04T14:16:00Z',external_execution:false};
          stats.events.unshift({action:'WORKER_DONE',actor:'visitor',at:'2026-11-04T14:16:00Z',reference:stats.command});
          return out({processed:1,external_execution:false,execution_type:'INTERNAL_VALIDATION_ONLY'});
        }
        if(path.endsWith('/enterprise/commands/'+stats.command))return out(comm());
        if(path.endsWith('/enterprise/what-if'))return out({side_effect:'NONE',workflow_unchanged:true,baseline_snapshot_sha256:'e'.repeat(64),proposed:{stock:80}});
        if(path.includes('/enterprise/reconciliation'))return out({status:'MATCH',differences:[],source:'NATIVE_A_RC8_DYNAMIC_AND_B_PG16'},201);
        if(path.endsWith('/enterprise/mcp/tools/call'))return out({read_only:true,tool:'mrp.get_run',result:{run}});
        if(path.endsWith('/enterprise/mcp/rpc'))return out({jsonrpc:'2.0',id:1,result:{tools:[{name:'mrp.get_run'}]}});
        return out({detail:'MOCK_ROUTE_NOT_FOUND',path},404);
      };
    }'''
    page.evaluate("Object.defineProperty(window.crypto, 'randomUUID', {value: () => '00000000-0000-4000-8000-000000000555', configurable: true});")
    page.evaluate(mock,manufacturing)
    for asset in ['engine.js','decision.js','decision-evidence.js','decision-reasoning.js','closure.js','portable.js','app.js','onboarding.js','enterprise-console.js']:
        page.add_script_tag(content=(SITE/asset).read_text(encoding='utf-8'))
    page.wait_for_selector('#vbConsoleNav',timeout=12000)
    page.locator('#vbConsoleNav').click()
    assert page.locator('#vbConsole').is_visible()
    assert not page.locator('#body').is_visible()
    assert page.get_by_text('MRP 企业闭环执行中心').count()>=1
    assert page.locator('[data-action="approve"]').is_disabled()
    assert page.locator('[data-action="dispatch"]').is_disabled()
    assert page.locator('.vbc-technical').get_attribute('open') is None
    print('01_BUSINESS_FIRST_AND_GATES=PASS')
    page.locator('[data-action="connect"]').click()
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("guest-test1")')
    page.locator('[data-action="create"]').click()
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("MRP-1234567890abcdef")')
    assert page.get_by_text('待人工审核').count()>=1
    assert page.locator('[data-action="approve"]').is_enabled()
    assert page.locator('[data-action="dispatch"]').is_disabled()
    assert page.get_by_text('总净需求量').count()>=1
    print('02_MRP_BUSINESS_SUMMARY_AND_APPROVAL_GATE=PASS')
    page.locator('[data-action="reason-template"]').select_option('MRP物料计划已核对，批准进入内部执行流程')
    page.locator('[data-action="approve"]').click()
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("审批通过，待执行校验")')
    assert page.locator('[data-action="approve"]').is_disabled()
    assert page.locator('[data-action="dispatch"]').is_enabled()
    print('03_APPROVAL_AND_EXECUTION_GATE=PASS')
    page.locator('[data-action="dispatch"]').click()
    page.wait_for_function('document.querySelector("#vbConsole").textContent.includes("内部校验已完成")')
    assert page.locator('[data-action="dispatch"]').is_disabled()
    assert page.get_by_text('执行回执单').count()>=1
    assert page.locator('.vbc-business-timeline li').count()>=3
    print('04_WORKER_RECEIPT_AUDIT_TIMELINE=PASS')
    page.screenshot(path=str(OUT/'RC33_BUSINESS_FIRST_DESKTOP.png'),full_page=True)
    page.locator('[data-action="reset-flow"]').click()
    assert page.locator('[data-action="approve"]').is_disabled()
    assert page.locator('[data-action="dispatch"]').is_disabled()
    assert not page.locator('.vbc-business-timeline li').count()
    assert page.locator('[data-action="create"]').is_enabled()
    print('05_RESET_CONTEXT_NOT_DATABASE=PASS')
    page.locator('[data-tab="orders"]').click()
    assert not page.locator('#vbConsole').is_visible()
    assert page.locator('#body').is_visible()
    print('06_SIMULATION_WORKSPACE_PRESERVED=PASS')
    page.set_viewport_size({'width':390,'height':844})
    page.locator('#sidebarToggle').click()
    page.locator('#vbConsoleNav').click()
    assert page.locator('#vbConsole').is_visible()
    page.screenshot(path=str(OUT/'RC33_BUSINESS_FIRST_MOBILE.png'),full_page=True)
    print('07_MOBILE_WORKSPACE=PASS')
    assert not errors,errors
    assert "localStorage.setItem('v19b_last_run_id'" in (SITE/'enterprise-console.js').read_text(encoding='utf-8')
    assert "localStorage.setItem('v19b_token'" not in (SITE/'enterprise-console.js').read_text(encoding='utf-8')
    print('08_NO_PAGE_ERRORS_OR_CREDENTIAL_STORAGE=PASS')
    calls=page.evaluate('window.__httpMock.calls')
    for endpoint in ['/mrp/runs','/decisions','/worker/dispatch','/review/overview/']:
        assert any(endpoint in path for method,path in calls),endpoint
    (OUT/'RC33_BROWSER_MOCK_CALLS.json').write_text(json.dumps(calls,ensure_ascii=False,indent=2),encoding='utf-8')
    print('09_API_CONTRACTS_EXERCISED=PASS')
    # RC3.4: selecting scenario B must actually change the POST payload.
    page.locator('[data-bind="scenario"]').select_option('B')
    page.locator('[data-action="create"]').click()
    page.wait_for_function('window.__httpMock.createPayloads.length >= 2')
    assert page.evaluate('window.__httpMock.createPayloads.at(-1).scenario')=='B'
    print('10_SCENARIO_B_SENT_TO_BACKEND=PASS')
    # A rejected plan must be terminal, with approval and dispatch disabled.
    page.locator('[data-action="reject"]:not([disabled])').wait_for(timeout=12000)
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator('[data-action="reject"]').click()
    page.wait_for_function('window.__httpMock.state === "REJECTED"',timeout=3000)
    assert page.locator('[data-action="approve"]').is_disabled()
    assert page.locator('[data-action="reject"]').is_disabled()
    assert page.locator('[data-action="dispatch"]').is_disabled()
    print('11_REJECTED_TERMINAL_GATES=PASS')
    for scenario in ('C','D','A'):
        page.locator('[data-action="reset-flow"]').click()
        page.locator('[data-bind="scenario"]').select_option(scenario)
        page.locator('[data-action="create"]').click()
        page.wait_for_function('(n)=>window.__httpMock.createPayloads.length>=n',arg={'C':3,'D':4,'A':5}[scenario])
        assert page.evaluate('window.__httpMock.createPayloads.at(-1).scenario')==scenario
        page.locator('[data-action="approve"]:not([disabled])').wait_for(timeout=12000)
    print('12_ALL_FOUR_SCENARIO_REQUESTS=PASS')
    browser.close()
