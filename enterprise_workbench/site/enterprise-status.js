/* Cloud RC2: Version B first-class enterprise workspace with transient visitor sessions. */
(async function(){
 'use strict';
 const base='/api/v1/version-b/enterprise';
 const ENTERPRISE_READY='/ready';
 let bearer='',currentRun='',commandId='',lastIdentity=null,pending=false;
 const style=document.createElement('style');
 style.textContent=`#rc2Open{position:fixed;right:14px;bottom:14px;z-index:9999;border:1px solid #7293b9;background:#152a45;color:#fff;border-radius:12px;padding:11px 14px;font:13px system-ui;cursor:pointer;box-shadow:0 6px 20px #0003}
 #rc2Pane{position:fixed;right:12px;bottom:62px;z-index:9999;max-height:78vh;overflow:auto;width:min(440px,calc(100vw - 24px));background:#11243b;color:#e8f3ff;border:1px solid #7293b9;border-radius:12px;padding:18px;box-shadow:0 14px 35px #0006;font:13px/1.6 system-ui}
 #rc2Pane[hidden]{display:none}#rc2Pane button{border:1px solid #6c9bcd;border-radius:7px;background:#1d3e63;color:white;padding:7px 10px;margin:4px;cursor:pointer}#rc2Pane button:disabled{opacity:.45;cursor:not-allowed}
 #rc2Pane input,#rc2Pane textarea{width:100%;box-sizing:border-box;background:#fff;color:#111;padding:7px;margin:4px 0 9px;border-radius:5px;border:1px solid #aaa}#rc2Pane pre{white-space:pre-wrap;overflow-wrap:anywhere;border:1px solid #536d8f;background:#091a2d;padding:10px;border-radius:7px;max-height:180px;overflow:auto}#rc2Pane small{color:#b8c9da}#rc2Pane .rc2warn{color:#f5cb8c}`;
 document.head.appendChild(style);
 const open=document.createElement('button');open.id='rc2Open';open.type='button';open.textContent='Version B · 企业事务';document.body.appendChild(open);
 const pane=document.createElement('section');pane.id='rc2Pane';pane.hidden=true;pane.setAttribute('aria-label','Version B 企业事务操作面板');
 pane.innerHTML=`<h3 style="margin:0 0 7px">Version B · RC2 企业事务</h3>
 <small>真实 PostgreSQL 持久化演示，区别于左侧其他浏览器模拟页面。每次连接生成全新隔离租户，不写入真实 ERP/MES/SRM。</small>
 <p id="rc2Ready" class="rc2warn">正在探测服务端…</p>
 <p id="rc2DemoHint">公开预览会为每位访客分配独立的临时租户。数据不会写入外部 ERP/MES/SRM。</p>
 <input type="password" id="rc2Token" autocomplete="off" hidden aria-label="内部预览令牌">
 <button id="rc2Connect" type="button">开始独立演示会话</button><button id="rc2Clear" type="button">退出</button>
 <hr><div>当前租户/角色：<strong id="rc2Who">未登录</strong></div>
 <p>Run ID：<input type="text" id="rc2Run" placeholder="MRP-...（可粘贴已有运行号）"></p>
 <button id="rc2Mrp" type="button">PG16 创建 MRP</button>
 <button id="rc2Read" type="button">读取后端运行</button>
 <button id="rc2Workflow" type="button">读取 Workflow / 审计</button>
 <label>人工审核原因<input type="text" id="rc2Reason" value="RC2 integration demonstration"></label>
 <button id="rc2Approve" type="button">真实审批：批准</button><button id="rc2Reject" type="button">真实审批：驳回</button>
 <button id="rc2Worker" type="button">触发内部 Worker</button>
 <button id="rc2Receipt" type="button">查看持久化回执</button>
 <button id="rc2Mcp" type="button">MCP 只读查询</button>
 <button id="rc2Recon" type="button">A/B 同快照校验</button>
 <p class="rc2warn">A/B 校验必须使用同一规范化快照。RC8 本地场景与 PG16 输入不同会显示 SNAPSHOT_MISMATCH，不会伪造一致结果。</p>
 <pre id="rc2Output" role="status" aria-live="polite">请选择操作；未连接时全部企业动作拒绝。</pre>`;
 // Keep all RC1 action handlers unchanged; elevate their panel to a full Workbench page.
 const mainContent=document.querySelector('main.main .content');
 const nav=document.getElementById('nav');
 const tab=document.createElement('button');tab.type='button';tab.id='vbEnterpriseTab';tab.className='nav';
 tab.textContent='▣ Version B · 企业闭环';tab.setAttribute('aria-controls','vbEnterprisePage');
 if(nav)nav.appendChild(tab);
 const workspace=document.createElement('section');workspace.id='vbEnterprisePage';workspace.hidden=true;
 workspace.setAttribute('aria-label','Version B 企业工作流、审批、Worker 和审计');
 workspace.innerHTML='<div class="vb-enterprise-intro"><div><span class="vb-eyebrow">ENTERPRISE WORKFLOW / POSTGRESQL 16</span><h1>Version B · 企业闭环工作台</h1><p>独立访客租户 · 持久化 MRP · 审批 · Worker · 回执 · 审计 · MCP · A/B 对账</p></div><strong class="vb-chip">ISOLATED DEMO</strong></div>';
 if(mainContent){mainContent.appendChild(workspace);open?.setAttribute('title','打开 Version B 企业工作台')}
 workspace.appendChild(pane);pane.hidden=false;
 const pageCss=document.createElement('style');
 pageCss.textContent=`.content.vb-mode > :not(#vbEnterprisePage){display:none!important}
 #vbEnterprisePage[hidden]{display:none!important}
 #vbEnterprisePage{padding:8px 0 35px;min-height:70vh}
 #vbEnterprisePage .vb-enterprise-intro{display:flex;justify-content:space-between;align-items:center;gap:18px;margin:2px 0 22px}
 #vbEnterprisePage h1{margin:5px 0 4px;font-size:25px}
 #vbEnterprisePage .vb-enterprise-intro p{margin:0;color:var(--muted,#8d99aa)}
 #vbEnterprisePage .vb-eyebrow{font-size:11px;letter-spacing:1.5px;color:#4eb5d9}
 #vbEnterprisePage .vb-chip{border:1px solid #397596;border-radius:16px;padding:5px 10px;white-space:nowrap;font-size:11px}
 #vbEnterprisePage #rc2Pane{position:static;max-height:none;overflow:visible;width:100%;max-width:100%;box-sizing:border-box;box-shadow:none;border-radius:12px;padding:clamp(16px,3vw,30px)}
 #vbEnterprisePage #rc2Pane button{margin:5px 7px 5px 0}
 #vbEnterprisePage #rc2Pane input{max-width:620px;display:block}
 #vbEnterprisePage #rc2Pane pre{max-height:380px}
 #vbEnterprisePage #rc2Pane button:focus-visible{outline:2px solid #64c8ed;outline-offset:3px}
 #vbEnterpriseTab.active{border-left:3px solid #64c8ed}
 @media(max-width:700px){#vbEnterprisePage .vb-enterprise-intro{display:block}#vbEnterprisePage h1{font-size:21px}}
 `;
 document.head.appendChild(pageCss);
 let showing=false;
 function showEnterprise(){
   if(!mainContent){pane.hidden=false;return}
   showing=true;mainContent.classList.add('vb-mode');workspace.hidden=false;open.hidden=true;
   document.querySelectorAll('#nav .nav').forEach(el=>el.classList.toggle('active',el===tab));
   const crumb=document.getElementById('crumb');if(crumb)crumb.textContent='Version B · 企业闭环';
   document.body.classList.remove('sidebar-open');tab.setAttribute('aria-current','page');
 }
 function hideEnterprise(){
   if(!showing)return;
   showing=false;mainContent.classList.remove('vb-mode');workspace.hidden=true;open.hidden=false;
   tab.classList.remove('active');tab.removeAttribute('aria-current');
 }
 tab.onclick=showEnterprise;
 if(nav)nav.addEventListener('click',ev=>{if(ev.target.closest('[data-tab]'))hideEnterprise()});
 const q=id=>pane.querySelector('#'+id),out=x=>{q('rc2Output').textContent=typeof x==='string'?x:JSON.stringify(x,null,2)};
 open.onclick=showEnterprise;
 async function call(path,{method='GET',body=null,auth=true}={}){
  if(auth&&!bearer)throw Error('请先验证服务端凭据');
  const controller=new AbortController();const deadline=setTimeout(()=>controller.abort(),30000);
  let response;try{response=await fetch(base+path,{method,cache:'no-store',signal:controller.signal,headers:{...(auth?{'Authorization':'Bearer '+bearer}:{}),...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined})}catch(e){if(e.name==='AbortError')throw Error('请求超时，请检查 Render 是否正在唤醒');throw e}finally{clearTimeout(deadline)}
  const data=await response.json().catch(()=>({detail:'INVALID_RESPONSE'}));
  if(!response.ok){if(response.status===401){bearer='';lastIdentity=null;applyRoles();}throw Error('HTTP '+response.status+' · '+JSON.stringify(data.detail||data))}
  return data;
 }
 async function perform(fn){if(pending){out('前一操作正在执行，请勿重复提交');return;}pending=true;try{out(await fn())}catch(e){out('操作拒绝 / 未通过：'+e.message)}finally{pending=false;applyRoles()}}
 const roleAllowed=(...roles)=>!!lastIdentity&&roles.includes(lastIdentity.role);
 function applyRoles(){for(const [id,roles] of Object.entries({rc2Mrp:['planner','admin'],rc2Approve:['approver','admin'],rc2Reject:['approver','admin'],rc2Worker:['operator','admin'],rc2Recon:['planner','approver','admin'],rc4Verified:['planner','approver','admin'],rc4Dynamic:['planner','approver','admin'],rc4WhatIf:['planner','admin']}))q(id).disabled=!roleAllowed(...roles)}
 function run(){return q('rc2Run').value.trim()||currentRun}
 function key(){if(!globalThis.crypto?.randomUUID)throw Error('此操作需要安全上下文以生成幂等键');return crypto.randomUUID()}
 q('rc2Connect').onclick=()=>perform(async()=>{const ready=await fetch(ENTERPRISE_READY,{cache:'no-store'});if(!ready.ok)throw Error('PostgreSQL 未就绪（/ready HTTP '+ready.status+'），请检查 Render DATABASE_URL');const response=await fetch('/api/v1/version-b/preview/session',{method:'POST',cache:'no-store'});if(!response.ok)throw Error('无法启动演示会话 HTTP '+response.status);const preview=await response.json();bearer=preview.access_token;try{lastIdentity=await call('/me');q('rc2Who').textContent=`${lastIdentity.tenant} / ${lastIdentity.role} / ${lastIdentity.actor}`;applyRoles();return {connected:true,actor:lastIdentity.actor,tenant:lastIdentity.tenant,role:lastIdentity.role}}catch(e){bearer='';lastIdentity=null;applyRoles();throw e}finally{q('rc2Token').value=''}});
 q('rc2Clear').onclick=()=>{bearer='';lastIdentity=null;currentRun='';commandId='';q('rc2Token').value='';q('rc2Who').textContent='未登录';applyRoles();out('已退出；凭据未持久化')};
 q('rc2Mrp').onclick=()=>perform(async()=>{const data=await call('/mrp/runs',{method:'POST'});currentRun=data.run_id;q('rc2Run').value=currentRun;return data});
 q('rc2Read').onclick=()=>perform(()=>call('/mrp/runs/'+encodeURIComponent(run())));
 q('rc2Workflow').onclick=()=>perform(()=>call('/workflows/'+encodeURIComponent(run())));
 for(const [id,decision] of [['rc2Approve','APPROVED'],['rc2Reject','REJECTED']])q(id).onclick=()=>perform(async()=>{const data=await call('/decisions',{method:'POST',body:{run_id:run(),decision,reason:q('rc2Reason').value.trim(),idempotency_key:key()}});commandId=data.command_id;return data});
 q('rc2Worker').onclick=()=>perform(()=>call('/worker/dispatch',{method:'POST'}));
 q('rc2Receipt').onclick=()=>perform(()=>{if(!commandId)throw Error('本页面暂无 command_id，请先审批');return call('/commands/'+encodeURIComponent(commandId))});
 q('rc2Mcp').onclick=()=>perform(()=>call('/mcp/tools/call',{method:'POST',body:{tool:'mrp.get_run',arguments:{run_id:run()}}}));
 q('rc2Recon').onclick=()=>perform(async()=>{
   const id=document.getElementById('scenario')?.value||'normal';
   const raw=localStorage.getItem('v19-simulation-'+id);
   if(!raw)throw Error('尚无有效的 RC8 本地业务快照');
   const state=JSON.parse(raw);if(!state.run||state.run.revision!==state.revision)throw Error('RC8 模拟结果已过期，请先计算');
   // Do NOT silently substitute PG input for A input: this is an honest mismatch when scenarios differ.
   return call('/reconciliation',{method:'POST',body:{run_id:run(),a_snapshot:state,
      a_result:{...state.run,input_hash:'RC8_BROWSER_INPUT_NOT_CANONICAL'},idempotency_key:key()}});
 });

 // G4 is deliberately additive to RC2/G3; no frozen RC8 business JS is edited.
 const g4=document.createElement('section');g4.id='rc4Panel';
 g4.innerHTML=`<hr><h3 style="margin:8px 0">RC4 · 企业闭环操作</h3>
 <small>这里的计算来自独立 PG16 运行。What-if 只计算副本，绝不提交到审批或库存。</small>
 <div id="rc4Stage" role="status" aria-live="polite">未建立企业运行</div>
 <button id="rc4Overview" type="button">闭环总览 · 状态/审批/回执/审计</button>
 <button id="rc4Verified" type="button">冻结 RC8 基准对账</button>
 <button id="rc4Dynamic" type="button">原生 RC8 动态 A/B 对账</button>
 <button id="rc4ListMcp" type="button">MCP tools/list · 实际协议</button>
 <fieldset style="border:1px solid #496d91;border-radius:8px;padding:9px;margin:9px 0"><legend>PostgreSQL 快照 What-if（不修改持久化运行）</legend>
 <label>类型<select id="rc4Kind" aria-label="What-if 类型"><option value="stock">调整库存</option><option value="receipt">模拟到货</option><option value="due">调整订单交期</option></select></label>
 <label>物料 ID / 订单 ID<input id="rc4Target" placeholder="例如 BR-01 或 SO-2026-001"></label>
 <label>调整后的库存 / 到货数量<input id="rc4Qty" inputmode="decimal" type="number" min="0" step="any" value="80"></label>
 <label>到货日期 / 新交期<input id="rc4Date" type="date" value="2026-11-20"></label>
 <button id="rc4WhatIf" type="button">运行隔离 What-if</button>
 </fieldset>
 <button id="rc4CopyRun" type="button">复制当前 Run ID</button>
 <p class="rc2warn">动态 A/B 只有后端实际运行冻结的 RC8 JavaScript 引擎，才会返回可验证对账；缺少 Node 时明确拒绝，不退化为 B 对 B。</p>`;
 pane.insertBefore(g4,q('rc2Output'));
 const stage=q('rc4Stage');
 const setStage=(text)=>{stage.textContent=text};
 const oldMrp=q('rc2Mrp').onclick,oldClear=q('rc2Clear').onclick;
 q('rc2Mrp').onclick=async()=>{await oldMrp();if(run())setStage('运行号已生成，可执行审核 / What-if / 对账')};
 q('rc2Clear').onclick=()=>{oldClear();setStage('已退出；请重新验证角色身份')};
 q('rc4Overview').onclick=()=>perform(async()=>{
   if(!run())throw Error('请先创建或输入 Run ID');
   const data=await call('/review/overview/'+encodeURIComponent(run()));
   const cmd=data.command?.status||'尚无执行命令';
   setStage('Workflow: '+data.workflow.state+' · Worker: '+cmd+' · 外部写入: 否');
   if(data.command?.command_id)commandId=data.command.command_id;
   return data;
 });
 q('rc4Verified').onclick=()=>perform(()=>call('/reconciliation/verified',{method:'POST',body:{run_id:run(),idempotency_key:key()}}));
 q('rc4Dynamic').onclick=()=>perform(()=>call('/reconciliation/dynamic',{method:'POST',body:{run_id:run(),idempotency_key:key()}}));
 q('rc4ListMcp').onclick=()=>perform(()=>call('/mcp/rpc',{method:'POST',body:{jsonrpc:'2.0',id:1,method:'tools/list',params:{}}}));
 q('rc4WhatIf').onclick=()=>perform(async()=>{
   const body={run_id:run(),kind:q('rc4Kind').value,target:q('rc4Target').value.trim(),
     quantity:q('rc4Qty').value,date:q('rc4Date').value};
   if(!body.run_id||!body.target)throw Error('请填写运行号和合法目标 ID');
   const data=await call('/what-if',{method:'POST',body});
   if(data.side_effect!=='NONE'||data.workflow_unchanged!==true)throw Error('What-if 安全契约不满足');
   setStage('What-if 已计算 · 持久化快照和审批未更改');
   return data;
 });
 q('rc4Kind').onchange=()=>{
   const due=q('rc4Kind').value==='due';
   q('rc4Qty').disabled=due;
   q('rc4Target').placeholder=due?'例如 SO-2026-001':'例如 BR-01';
 };
 q('rc4CopyRun').onclick=()=>perform(async()=>{
   if(!run())throw Error('暂无 Run ID');
   if(!navigator.clipboard?.writeText)throw Error('仅在安全上下文支持复制，请手动选中 Run ID');
   await navigator.clipboard.writeText(run());
   return 'Run ID 已复制（非访问令牌）';
 });
 applyRoles();
 try{const ready=await fetch(ENTERPRISE_READY,{cache:'no-store'});if(!ready.ok){q('rc2Ready').textContent='PostgreSQL 尚未就绪（/ready HTTP '+ready.status+'）· 请检查 Render DATABASE_URL';q('rc2Ready').className='rc2warn';}else{q('rc2Ready').textContent='PostgreSQL 已就绪 · 可启动访客演示';q('rc2Ready').className='';}}catch(e){q('rc2Ready').textContent='数据库探测失败：'+e.message;}
 try{const r=await fetch('/api/v1/version-b/capabilities',{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const cap=await r.json();if(cap.production_ready!==false)throw Error('Contract guard: unexpected production status');if(!q('rc2Ready').textContent.includes('尚未就绪')&&!q('rc2Ready').textContent.includes('探测失败')){q('rc2Ready').textContent='PostgreSQL 已就绪 · 可启动访客演示';q('rc2Ready').className=''}}catch(e){q('rc2Ready').textContent='后端未就绪 · RC8 浏览器模拟仍可独立使用';}
})();
