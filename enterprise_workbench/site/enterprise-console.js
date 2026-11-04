/* Industrial AI PaaS Lab — Version B Enterprise Console RC3.
 * UI-only, cumulative on RC2. All business state comes from the RC2 backend.
 * No credential persistence, cross-tenant run sharing or external ERP/MES/SRM writes.
 */
(()=>{
'use strict';
const api='/api/v1/version-b/enterprise';
const main=document.querySelector('main.main .content');
const nav=document.getElementById('nav');
if(!main||!nav) return;
const E=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
const asText=x=>x===null||x===undefined||x===''?'—':String(x);
const viewNames={mrp:'MRP 运行详情',approval:'审批中心',execution:'执行监控',receipt:'回执详情',audit:'审计时间线'};
const tabs=['mrp','approval','execution','receipt','audit'];
const state={ready:false,readiness:'检查 PostgreSQL 连接中',session:null,token:'',runId:'',commandId:'',run:null,overview:null,command:null,workflow:null,view:'mrp',busy:false,message:null,reason:'已核对物料计划，批准进行内部验证',runInput:'',lineSearch:'',linePage:1,lineKind:'requirements',whatif:{kind:'stock',target:'BR-01',quantity:'80',date:'2026-11-20'},advanced:null,advancedResponse:null,raw:null, lastWorker:null};
const root=document.createElement('section');root.id='vbConsole';root.hidden=true;root.setAttribute('aria-label','Version B 企业级运行闭环工作台');
main.appendChild(root);
const button=document.createElement('button');button.id='vbConsoleNav';button.className='nav';button.type='button';button.textContent='▣ 企业执行中心 · Version B';button.setAttribute('aria-controls','vbConsole');nav.appendChild(button);
let showing=false;
function activate(){showing=true;document.body.classList.add('vbc-body-active');main.classList.add('vbc-active');root.hidden=false;document.querySelectorAll('#nav .nav').forEach(x=>x.classList.toggle('active',x===button));document.getElementById('crumb').textContent='企业执行中心';document.body.classList.remove('sidebar-open');button.setAttribute('aria-current','page');render();}
function deactivate(){if(!showing)return;showing=false;document.body.classList.remove('vbc-body-active');main.classList.remove('vbc-active');root.hidden=true;button.classList.remove('active');button.removeAttribute('aria-current');}
button.addEventListener('click',activate);
nav.addEventListener('click',e=>{if(e.target.closest('[data-tab]'))deactivate()});
const badge=(value,kind)=>`<span class="vbc-chip ${E(kind||tone(value))}">${E(asText(value))}</span>`;
function tone(v){if(['DONE','EXECUTED_INTERNAL','APPROVED','COMPLETED','READ_SUCCESS'].includes(v))return 'ok';if(['PENDING','APPROVED_QUEUED','CLAIMED','RUNNING','RETRY','RETRY_PENDING'].includes(v))return 'info';if(['WAITING_REVIEW','NOT_EXECUTED','NO_RUN'].includes(v))return 'warn';if(['REJECTED','FAILED_TERMINAL','DEAD','FAILED'].includes(v))return 'bad';return 'muted';}
function status(){return state.overview?.workflow?.state||state.workflow?.state||(state.run?'WAITING_REVIEW':'NO_RUN')}
function command(){return state.command||state.overview?.command||null}
function decision(){return state.overview?.decision||null}
function isReady(){return !!state.token&&!!state.session}
function hasRun(){return isReady()&&!!state.runId&&!!state.run}
function isReviewable(){return hasRun()&&status()==='WAITING_REVIEW'}
function canExecute(){return hasRun()&&decision()?.type==='APPROVED'&&!!(state.commandId||command()?.command_id)&&!['DONE','DEAD'].includes(command()?.status)}
function busyAttr(ok=true){return !ok||state.busy?'disabled':''}
function stat(label,val,foot){return `<div class="vbc-stat"><span class="vbc-stat-label">${E(label)}</span><div class="vbc-stat-value">${E(asText(val))}</div><div class="vbc-stat-foot">${E(foot||'')}</div></div>`;}
function callout(content,kind=''){return `<div class="vbc-callout ${kind}">${content}</div>`;}
function empty(title,desc){return `<div class="vbc-empty"><strong>${E(title)}</strong>${E(desc)}</div>`;}
function pair(k,v){return `<div class="vbc-detail-row"><dt>${E(k)}</dt><dd>${E(asText(v))}</dd></div>`;}
function labelNum(n){return Number.isFinite(Number(n))?Number(n).toLocaleString('zh-CN',{maximumFractionDigits:3}):asText(n)}
function formatTime(v){if(!v)return '—';const d=new Date(v);return Number.isNaN(d.getTime())?String(v):d.toLocaleString('zh-CN',{hour12:false});}
function raw(){return `<details class="vbc-data-drawer"><summary>技术核验 · 查看最近一次真实 API 返回（非页面模拟数据）</summary><pre>${E(JSON.stringify(state.raw??{message:'尚无接口结果'},null,2))}</pre></details>`}
function head(){const w=status();const stepsDone={mrp:!!state.run,approval:!!decision(),execution:!!command()&&['DONE','DEAD'].includes(command().status),receipt:!!command()?.receipt,audit:!!state.overview&&!!state.run};return `
<div class="vbc-hero"><div class="vbc-hero-grid"><div><div class="vbc-eyebrow">INDUSTRIAL / AI · ENTERPRISE OPERATIONS</div><h1>从 MRP 到执行回执，每一步有据可查</h1><p>五段可追溯业务流程 · FastAPI / PostgreSQL 16 · 内部 Worker · 审批与审计。此处的结果来自真实后端，而非浏览器本地模拟。</p></div><div class="vbc-hero-side"><span class="vbc-status ${state.ready?'ready':'warn'}"><span class="vbc-dot"></span>${E(state.readiness)}</span><code>${E(state.session?state.session.tenant+' / '+state.session.role:'尚未建立访客会话')}</code>${isReady()?'<button class="vbc-btn ghost tiny" data-action="logout">退出当前会话</button>':`<button class="vbc-btn primary" data-action="connect" ${busyAttr(state.ready)}>开始独立演示</button>`}</div></div></div>
<div class="vbc-strip">${stat('当前工作流状态',w,'后端业务状态')}${stat('当前运行 Run ID',state.runId?state.runId:'尚未创建','仅限当前临时租户')}${stat('审批结果',decision()?.type||'待处理','决策持久化于 PostgreSQL')}${stat('命令执行状态',command()?.status||'未下发','内部验证 · 非外部生产')}</div>
<nav class="vbc-stepper" aria-label="企业业务闭环步骤">${tabs.map((t,i)=>`<button class="vbc-step ${state.view===t?'active':''} ${stepsDone[t]?'done':''}" type="button" data-action="nav" data-view="${t}" ${state.busy?'disabled':''} aria-current="${state.view===t?'step':'false'}"><span class="vbc-step-num">${stepsDone[t]?'✓':i+1}</span><span><span class="vbc-step-title">${viewNames[t]}</span><span class="vbc-step-sub">${['计划与物料','审核与授权','异步与状态','结果和凭证','事件和追溯'][i]}</span></span></button>`).join('')}</nav>`;}
function paneHeader(title,desc,extra=''){return `<div class="vbc-pane-head"><div><h2>${title}</h2><p>${desc}</p></div>${extra}</div>`}
function pendingMessage(){return !isReady()?callout('请先点击上方「开始独立演示」，完成 PostgreSQL 就绪检查并领取隔离访客会话。','warn'):'';}
function runTable(){const lines=state.lineKind==='requirements'?state.run?.lines:state.run?.pegs;if(!Array.isArray(lines))return empty('尚无计划明细','创建 MRP 后即可查看物料需求和供需追溯。');const q=state.lineSearch.trim().toLowerCase();const filtered=lines.filter(l=>!q||Object.values(l).some(v=>String(v).toLowerCase().includes(q)));const maxPage=Math.max(1,Math.ceil(filtered.length/12));state.linePage=Math.min(state.linePage,maxPage);const page=filtered.slice((state.linePage-1)*12,state.linePage*12);const pegging=state.lineKind==='pegging';const columns=pegging?['物料','日期','关联订单','毛需求','库存分配','在途分配','计划供应']:['物料','需求日期','毛需求','净需求','计划量','结余'];const fields=pegging?['material','date','order_id','gross','from_stock','from_receipts','from_planned']:['material','date','gross','net','planned','closing'];return `<div class="vbc-action-row"><button class="vbc-btn tiny ${!pegging?'primary':''}" data-action="line-kind" data-value="requirements">物料需求行 · ${state.run.lines.length}</button><button class="vbc-btn tiny ${pegging?'primary':''}" data-action="line-kind" data-value="pegging">供需追溯 · ${state.run.pegs.length}</button></div><label class="vbc-field">筛选物料 / 订单 / 日期<input id="vbSearch" data-bind="lineSearch" value="${E(state.lineSearch)}" placeholder="例如 BR-01、2026-11-30"></label><div class="vbc-table-wrap"><table class="vbc-table"><thead><tr>${columns.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>${page.map(row=>`<tr>${fields.map((f,i)=>`<td class="${i===0?'strong':''}">${E(asText(row[f]))}</td>`).join('')}</tr>`).join('')||`<tr><td colspan="${fields.length}">无匹配数据</td></tr>`}</tbody></table></div><div class="vbc-action-row"><span class="vbc-low">筛选后 ${filtered.length} 条 · 第 ${state.linePage} / ${maxPage} 页</span><button class="vbc-btn tiny" data-action="page-prev" ${busyAttr(state.linePage>1)}>上一页</button><button class="vbc-btn tiny" data-action="page-next" ${busyAttr(state.linePage<maxPage)}>下一页</button></div>`;}
function mrpPage(){const d=state.run;return `<div class="vbc-pane">${paneHeader('01 / MRP 运行详情','创建一次真实的 PostgreSQL MRP 运行，查看物料净需求、供需追溯和规范化快照。',badge(state.ready?'PG16 READY':'DB PENDING'))}<div class="vbc-pane-body">${pendingMessage()}${callout('<b>数据边界：</b>企业 MRP 使用 Neon 中预置的工业电机订单、BOM 和库存样例；左侧原始「MRP 计划」仍是浏览器本地模拟，两者不会自动同步。')}<div class="vbc-action-row"><button class="vbc-btn primary" data-action="create" ${busyAttr(isReady())}>＋ 创建 PostgreSQL MRP</button><span class="vbc-low">创建后生成不可变 Run ID 和计算快照。</span></div><div class="vbc-runbar"><label class="vbc-field">Run ID · 查询当前租户已创建的运行<input data-bind="runInput" value="${E(state.runInput||state.runId)}" placeholder="MRP-xxxxxxxxxxxxxxxx" maxlength="128"></label><button class="vbc-btn" data-action="lookup" ${busyAttr(isReady())}>读取运行</button><button class="vbc-btn tiny" data-action="copy-run" ${busyAttr(!!state.runId)}>复制编号</button></div>${d?`<div class="vbc-grid3"><div class="vbc-mini"><span class="label">物料需求行</span><div class="num">${d.lines?.length??0}</div><small>数据库明细</small></div><div class="vbc-mini"><span class="label">Pegging 追溯行</span><div class="num">${d.pegs?.length??0}</div><small>供应来源分解</small></div><div class="vbc-mini"><span class="label">计划计算状态</span><div class="num" style="font-size:17px">${E(asText(d.status))}</div><small>${E(asText(d.rule_version))}</small></div></div><div class="vbc-section-label">本次输入证据</div><div class="vbc-detail-list">${pair('输入快照指纹',state.overview?.snapshot_hash||d.input_hash)}${pair('业务基准日',d.snapshot?.as_of)}${pair('数据访问边界','按当前访客租户隔离 · 后端规范化快照')}${pair('运行编号',state.runId)}</div><h3 style="font-size:14px;margin:22px 0 6px">计划明细 / 供应分配</h3>${runTable()}`:empty('还没有企业 MRP 运行','连接会话后点击「创建 PostgreSQL MRP」，数据从后端读取并可继续审批。')}${raw()}</div></div>${advancedPanel()}`}
function approvalPage(){const dec=decision(),review=isReviewable();return `<div class="vbc-pane">${paneHeader('02 / 审批中心','审批是正式的后端决策：先校验当前 MRP 运行，再生成可追溯的批准或驳回记录。',badge(status()))}<div class="vbc-pane-body">${pendingMessage()}${!hasRun()?empty('当前尚无待审批运行','请先回到 MRP 运行详情创建计划。'):''}<div class="vbc-two"><div><div class="vbc-section-label">本次运行</div><div class="vbc-detail-list">${pair('Run ID',state.runId)}${pair('工作流',status())}${pair('净需求计划',state.run?.lines?.length+' 条明细')}${pair('审批决策',dec?.type||'等待审核')}</div>${dec?callout('该 Run ID 已有最终审批记录。本演示不允许对同一运行反复改变审批结论。','success'):callout('审批提交前可切回 MRP 页面核对明细和快照指纹。批准后才进入执行队列。')}</div><div><label class="vbc-field">审核原因（3–1000 字）<textarea data-bind="reason" maxlength="1000" placeholder="说明为什么批准或驳回本次计划">${E(state.reason)}</textarea></label><div class="vbc-action-row"><button class="vbc-btn teal" data-action="approve" ${busyAttr(review)}>✓ 批准并进入执行队列</button><button class="vbc-btn danger" data-action="reject" ${busyAttr(review)}>驳回本次计划</button></div><p class="vbc-low">批准请求在 PostgreSQL 中记录审批人、原因、命令编号和审计事件。驳回后不会生成可执行的 Outbox 任务。</p></div></div>${dec?`<div class="vbc-section-label">已持久化的审批记录</div><div class="vbc-detail-list">${pair('审批决定',dec.type)}${pair('审批原因',dec.reason)}${pair('审批人',dec.actor)}${pair('审批时间',formatTime(dec.at))}${pair('Command ID',command()?.command_id||state.commandId)}</div><div class="vbc-action-row"><button class="vbc-btn primary" data-action="nav" data-view="${dec.type==='APPROVED'?'execution':'audit'}">${dec.type==='APPROVED'?'下一步：执行监控 →':'查看审计记录 →'}</button></div>`:''}${raw()}</div></div>`;}
function executionPage(){const cmd=command();return `<div class="vbc-pane">${paneHeader('03 / 执行监控','审批通过后，经 Outbox 提交内部验证任务，由 Worker 处理并写入执行状态。',badge(cmd?.status||'NOT_DISPATCHED'))}<div class="vbc-pane-body">${pendingMessage()}<div class="vbc-grid3"><div class="vbc-mini"><span class="label">审批授权</span><div class="num" style="font-size:18px">${E(decision()?.type||'未审批')}</div><small>必须先批准</small></div><div class="vbc-mini"><span class="label">Outbox 状态</span><div class="num" style="font-size:18px">${E(cmd?.status||'无命令')}</div><small>由服务器返回</small></div><div class="vbc-mini"><span class="label">尝试次数</span><div class="num">${E(cmd?.attempts??'—')}</div><small>数据库值</small></div></div><div class="vbc-detail-list">${pair('Command ID',cmd?.command_id||state.commandId)}${pair('关联 MRP',cmd?.run_id||state.runId)}${pair('最近一次异常',cmd?.last_error||'无')}${pair('外部 ERP/MES/SRM 写入','否 · INTERNAL_VALIDATION_ONLY')}</div>${callout('执行范围说明：Worker 真正处理后端队列并产生数据库回执，但只执行内部业务规则校验。它不会启动真实工厂生产任务。','warn')}<div class="vbc-action-row"><button class="vbc-btn primary" data-action="dispatch" ${busyAttr(canExecute())}>▶ 触发内部 Worker</button><button class="vbc-btn" data-action="refresh" ${busyAttr(hasRun())}>↻ 刷新状态</button><button class="vbc-btn" data-action="nav" data-view="receipt" ${busyAttr(hasRun()&&!!(state.commandId||cmd?.command_id))}>查看回执 →</button></div>${state.lastWorker?`<div class="vbc-section-label">最近一次 Worker 调用结果</div><div class="vbc-detail-list">${pair('返回的处理情况',JSON.stringify(state.lastWorker.processed))}${pair('执行类型',state.lastWorker.execution_type)}${pair('外部系统操作',state.lastWorker.external_execution?'存在':'无')}</div>`:''}${!decision()?empty('等待审批','先在审批中心批准 MRP，随后才会生成 Outbox 待执行命令。'):''}${raw()}</div></div>`;}
function receiptPage(){const cmd=command();const receipt=cmd?.receipt;return `<div class="vbc-pane">${paneHeader('04 / 回执详情','从数据库按 Command ID 查询回执；审批成功、命令已入队与执行完成是三种不同状态。',badge(cmd?.status||'NO_COMMAND'))}<div class="vbc-pane-body">${pendingMessage()}${cmd?`<div class="vbc-grid3"><div class="vbc-mini"><span class="label">命令状态</span><div class="num" style="font-size:19px">${E(cmd.status)}</div><small>真实 Outbox 状态</small></div><div class="vbc-mini"><span class="label">执行尝试</span><div class="num">${E(cmd.attempts)}</div><small>Worker 记录</small></div><div class="vbc-mini"><span class="label">回执入库</span><div class="num" style="font-size:19px">${receipt?'已持久化':'尚未生成'}</div><small>不能将 PENDING 当成 DONE</small></div></div><div class="vbc-detail-list">${pair('Command ID',cmd.command_id)}${pair('Run ID',cmd.run_id)}${pair('审批决定',cmd.decision)}${pair('命令状态',cmd.status)}${pair('执行人/请求人',cmd.actor)}${pair('最近一次错误',cmd.last_error||'无')}</div><div class="vbc-section-label">执行回执内容（服务端原始字段）</div>${receipt?`<div class="vbc-callout success"><b>数据库回执已生成。</b> 此结果只证明平台内部验证执行，不证明物理生产动作。</div><div class="vbc-detail-list">${Object.entries(receipt).slice(0,18).map(([k,v])=>pair(k,typeof v==='object'?JSON.stringify(v):v)).join('')}</div>`:empty('暂无持久化执行回执','审批已批准但 Worker 尚未成功处理时，回执不会提前出现。')}<div class="vbc-action-row"><button class="vbc-btn primary" data-action="receipt" ${busyAttr(hasRun()&&!!(state.commandId||cmd?.command_id))}>↻ 从 PostgreSQL 查询回执</button><button class="vbc-btn" data-action="nav" data-view="audit">下一步：审计时间线 →</button></div>`:empty('当前没有执行命令','请先创建 MRP 并批准计划。被驳回的运行不会产生可执行 Worker 回执。')}${raw()}</div></div>`;}
function auditPage(){const events=state.overview?.events||state.workflow?.events||[];const flow=state.overview?.workflow||state.workflow||{};const count=Array.isArray(events)?events.length:0;return `<div class="vbc-pane">${paneHeader('05 / 审计时间线','按当前 Run ID 查阅真实审批与执行事件，时间、角色和引用编号来自 PostgreSQL。',badge(flow.state||'NO_RUN'))}<div class="vbc-pane-body">${pendingMessage()}<div class="vbc-grid3"><div class="vbc-mini"><span class="label">当前工作流</span><div class="num" style="font-size:16px">${E(flow.state||'—')}</div><small>实时后端状态</small></div><div class="vbc-mini"><span class="label">Workflow 版本</span><div class="num">${E(flow.version??'—')}</div><small>数据库版本计数</small></div><div class="vbc-mini"><span class="label">审计事件</span><div class="num">${count}</div><small>最多显示服务器最近 30 条</small></div></div><div class="vbc-action-row"><button class="vbc-btn primary" data-action="refresh" ${busyAttr(hasRun())}>↻ 刷新审计记录</button><button class="vbc-btn" data-action="nav" data-view="mrp">返回 MRP 详情</button></div><div class="vbc-section-label">与运行 ${E(state.runId||'—')} 关联的事件</div>${count?`<ol class="vbc-timeline">${events.map((ev)=>`<li class="vbc-event ${['APPROVED','EXECUTED_INTERNAL','WORKER_DONE'].includes(ev.action)?'positive':''}"><strong>${E(asText(ev.action))}</strong><p>时间：${E(formatTime(ev.at))}　·　操作者：${E(asText(ev.actor))}</p><p>引用编号：${E(asText(ev.reference))}</p></li>`).join('')}</ol>`:empty('暂无已持久化的审计事件','创建 MRP 后请执行审批和 Worker，再刷新时间线。此处不伪造演示事件。')}${callout('审计时间线只展示服务器实际返回的事件；空列表不代表已经完成业务闭环。')}${raw()}</div></div>`;}
function advancedPanel(){return `<details class="vbc-pane" style="margin-top:18px" ${state.advanced?'open':''} id="vbAdvanced"><summary style="padding:17px 22px;cursor:pointer;color:#395e92;font-weight:750">高级实验工具 · What-if / A-B 对账 / MCP （非主闭环步骤）</summary><div class="vbc-pane-body"><div class="vbc-aux-grid"><div class="vbc-mini"><h3>隔离 What-if（不改变运行或审批）</h3><p>更改库存、模拟到货或交期，调用 RC2 后端 What-if，结果只用于分析。</p><div class="vbc-action-row"><label class="vbc-field" style="flex:1;min-width:145px">调整类型<select data-bind="whatif.kind"><option value="stock" ${state.whatif.kind==='stock'?'selected':''}>库存数量</option><option value="receipt" ${state.whatif.kind==='receipt'?'selected':''}>预计到货</option><option value="due" ${state.whatif.kind==='due'?'selected':''}>订单交期</option></select></label><label class="vbc-field" style="flex:1;min-width:145px">物料 / 订单 ID<input data-bind="whatif.target" value="${E(state.whatif.target)}"></label></div><div class="vbc-action-row"><label class="vbc-field" style="flex:1;min-width:130px">数量<input type="number" min="0" step="any" data-bind="whatif.quantity" value="${E(state.whatif.quantity)}" ${state.whatif.kind==='due'?'disabled':''}></label><label class="vbc-field" style="flex:1;min-width:145px">日期<input type="date" data-bind="whatif.date" value="${E(state.whatif.date)}"></label></div><button class="vbc-btn" data-action="whatif" ${busyAttr(hasRun())}>运行隔离 What-if</button></div><div class="vbc-mini"><h3>后端计算对账 / MCP 工具</h3><p>同快照验证，不会将不同输入下的业务差异伪装成一致。MCP 查询只读。</p><div class="vbc-action-row"><button class="vbc-btn" data-action="recon-reference" ${busyAttr(hasRun())}>冻结基准对账</button><button class="vbc-btn" data-action="recon-dynamic" ${busyAttr(hasRun())}>动态 A/B 对账</button></div><div class="vbc-action-row"><button class="vbc-btn" data-action="mcp-read" ${busyAttr(hasRun())}>MCP · 读取 MRP</button><button class="vbc-btn" data-action="mcp-list" ${busyAttr(isReady())}>MCP · tools/list</button></div></div></div>${state.advancedResponse?`<div class="vbc-section-label">高级工具返回</div><details class="vbc-data-drawer" open><summary>查看后端返回的核验结果</summary><pre>${E(JSON.stringify(state.advancedResponse,null,2))}</pre></details>`:''}</div></details>`;}
function render(){if(!root)return;const message=state.message?`<div class="vbc-toast ${E(state.message.kind||'')}" role="status">${E(state.message.text)}</div>`:'';const selected=({mrp:mrpPage,approval:approvalPage,execution:executionPage,receipt:receiptPage,audit:auditPage})[state.view];root.innerHTML=head()+message+selected()+`<div class="vbc-footer">独立演示租户 · 两小时临时会话（仅保存在当前页面内存） · 无外部工厂系统写入 · 企业流程结果可供技术核验 · 本页面运行于 Version B RC3.1 候选版</div>`;}
async function request(path,{method='GET',body=null,auth=true,timeout=30000}={}){
 if(auth&&!state.token)throw new Error('请先建立独立演示会话');
 const ctrl=new AbortController();const timer=setTimeout(()=>ctrl.abort(),timeout);
 let res;
 try{res=await fetch((path==='/ready'||path.startsWith('/api/'))?path:api+path,{method,signal:ctrl.signal,cache:'no-store',headers:{...(auth?{'Authorization':'Bearer '+state.token}:{}),...(body!==null?{'Content-Type':'application/json'}:{})},body:body===null?undefined:JSON.stringify(body)});}catch(e){if(e.name==='AbortError')throw Error('请求超时（30 秒），Render 可能正在唤醒；写入操作结果未知，请刷新状态核实后再决定是否操作');throw Error('网络请求失败：'+e.message);}finally{clearTimeout(timer)}
 let data;try{data=await res.json()}catch{data={detail:'INVALID_JSON_RESPONSE'}}
 if(!res.ok){if(res.status===401){clearSession();}throw Error('HTTP '+res.status+' · '+JSON.stringify(data.detail||data).slice(0,250));}
 state.raw={path:(path==='/ready'||path.startsWith('/api/'))?path:api+path,method,data:path.includes('/preview/session')?{status:'SESSION_ISSUED',token_redacted:true}:data};return data;
}
function clearSession(){state.token='';state.session=null;state.runId='';state.runInput='';state.commandId='';state.run=null;state.overview=null;state.command=null;state.workflow=null;state.lastWorker=null;state.advancedResponse=null;state.reason='已核对物料计划，批准进行内部验证';}
async function fetchRun(id){
 if(!id)throw Error('请填写 Run ID');
 const data=await request('/mrp/runs/'+encodeURIComponent(id));
 if(data.source!=='postgresql'||!Array.isArray(data.run?.lines)||!Array.isArray(data.run?.pegs))throw Error('MRP_RUN_CONTRACT_MISMATCH');
 // When browsing another MRP within the same tenant, never reuse the prior command or receipt.
 if(state.runId && state.runId!==id){state.commandId='';state.command=null;state.overview=null;state.workflow=null;state.lastWorker=null;state.advancedResponse=null;}
 state.run=data.run;state.runId=id;state.runInput=id;
 await fetchOverview();
 return data;
}
async function fetchOverview(){
 if(!state.runId)throw Error('无可查询的 Run ID');
 const overview=await request('/review/overview/'+encodeURIComponent(state.runId));
 if(!overview.workflow||overview.source!=='PERSISTED_POSTGRESQL')throw Error('OVERVIEW_CONTRACT_MISMATCH');
 // A run without a command must not inherit a prior run's Command ID.
 if(overview.run_id!==state.runId)throw Error('OVERVIEW_RUN_ID_MISMATCH');
 if(overview.command && overview.command.run_id!==state.runId)throw Error('OVERVIEW_COMMAND_RUN_MISMATCH');
 state.overview=overview;
 state.commandId=overview.command?.command_id||'';
 state.command=overview.command||null;
 return overview;
}
async function fetchCommand(){
 const cmdid=state.commandId||command()?.command_id;
 if(!cmdid)throw Error('尚未产生 Command ID，请先批准 MRP');
 const data=await request('/commands/'+encodeURIComponent(cmdid));
 if(data.command_id!==cmdid)throw Error('COMMAND_ID_MISMATCH');
 if(data.run_id!==state.runId)throw Error('COMMAND_RUN_ID_MISMATCH');
 state.command=data;state.commandId=data.command_id;return data;
}
function uuid(){if(!globalThis.crypto?.randomUUID)throw Error('需要 HTTPS 安全上下文来生成幂等键');return crypto.randomUUID()}
async function perform(action,handler){if(state.busy)return;state.busy=true;state.message={text:'正在向 PostgreSQL / FastAPI 请求…',kind:''};render();try{const result=await handler();state.message={text:result||'操作已完成。结果已从服务器返回。',kind:'success'};}catch(e){state.message={text:e.message||String(e),kind:'error'};}finally{state.busy=false;render();}}
async function action(name,el){
 if(name==='nav'){state.view=el.dataset.view;state.message=null;render();return;}
 if(name==='logout'){clearSession();state.message={text:'已退出当前访客租户。会话令牌不保存在浏览器存储中。',kind:'success'};render();return;}
 if(name==='line-kind'){state.lineKind=el.dataset.value;state.linePage=1;render();return;}
 if(name==='page-prev'||name==='page-next'){state.linePage=Math.max(1,state.linePage+(name==='page-next'?1:-1));render();return;}
 if(name==='copy-run'){if(state.runId){if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(state.runId);state.message={text:'已复制 Run ID（不含任何访客令牌）。',kind:'success'}}else{state.message={text:'请手动选择并复制 Run ID。',kind:''}}render();}return;}
 if(name==='reject'&&!window.confirm('确定驳回这次 MRP 吗？此操作将在后端持久化并终结该运行，不能重复批准。'))return;
 await perform(name,async()=>{
 switch(name){
 case 'connect':{
  const ready=await request('/ready',{auth:false});if(ready.status!=='ready')throw Error('Neon PostgreSQL 未就绪');
  state.ready=true;state.readiness='PostgreSQL 16 · 已连接';
  const issued=await request('/api/v1/version-b/preview/session',{method:'POST',auth:false});
  if(!issued.access_token||!issued.tenant)throw Error('访客会话响应缺少身份字段');
  state.token=issued.access_token;
  try{const who=await request('/me');if(who.tenant!==issued.tenant||!who.role)throw Error('访客身份校验不匹配');state.session=who;}
  catch(e){clearSession();throw e;}
  return '独立访客会话已建立（租户 '+state.session.tenant+'），现在可以创建 MRP';
 }
 case 'create':{
  const created=await request('/mrp/runs',{method:'POST'});if(!created.run_id||created.source!=='postgresql')throw Error('MRP_CREATE_CONTRACT_MISMATCH');
  state.runId=created.run_id;state.runInput=created.run_id;state.commandId='';state.command=null;state.overview=null;state.run=null;state.lineSearch='';state.linePage=1;state.lastWorker=null;
  try{await fetchRun(created.run_id);}catch(e){throw Error('MRP 已提交，Run ID='+created.run_id+'；但详情加载失败：'+e.message+'。请使用 Run ID 查询，避免重复创建。')}
  state.view='mrp';return 'MRP 已写入 PostgreSQL：'+created.run_id+'；可以查看明细并进入审批中心。';
 }
 case 'lookup':{const requested=state.runInput.trim();if(!requested)throw Error('请输入 Run ID');await fetchRun(requested);return '已从 PostgreSQL 载入当前租户的 MRP 运行：'+requested;}
 case 'refresh':{
  if(!hasRun())throw Error('请先创建 MRP');
  await fetchOverview();if(state.commandId)await fetchCommand();
  return '已从 PostgreSQL 更新工作流、Outbox、回执和审计状态';
 }
 case 'approve':case 'reject':{
  if(!isReviewable())throw Error('仅 WAITING_REVIEW 的运行可进行审批');
  const reason=state.reason.trim();if(reason.length<3||reason.length>1000)throw Error('审批原因需要 3–1000 字');
  const outcome=name==='approve'?'APPROVED':'REJECTED';
  const decided=await request('/decisions',{method:'POST',body:{run_id:state.runId,decision:outcome,reason,idempotency_key:uuid()}});
  if(!decided.command_id||decided.status!=='ACCEPTED')throw Error('审批响应契约不符合预期');
  state.commandId=decided.command_id;await fetchOverview();state.view=outcome==='APPROVED'?'execution':'audit';
  return outcome==='APPROVED'?'审批已保存，Outbox 命令已入队（尚未执行）':'驳回已保存；该运行不会执行 Worker';
 }
 case 'dispatch':{
  if(!canExecute())throw Error('没有可执行的已批准命令');
  const result=await request('/worker/dispatch',{method:'POST'});
  if(result.external_execution!==false)throw Error('WORKER_EXTERNAL_EXECUTION_GUARD');
  state.lastWorker=result;await fetchOverview();if(state.commandId)await fetchCommand();
  return 'Worker 请求已完成，数据库命令状态：'+asText(command()?.status)+'。请检查回执。';
 }
 case 'receipt':{await fetchCommand();await fetchOverview();return '已从 PostgreSQL 更新 Command ID '+state.commandId+' 的执行回执';}
 case 'whatif':{
  if(!hasRun())throw Error('请先创建 MRP');const w=state.whatif;
  if(!w.target.trim())throw Error('请填写合法的物料或订单 ID');
  const data=await request('/what-if',{method:'POST',body:{run_id:state.runId,kind:w.kind,target:w.target.trim(),quantity:w.kind==='due'?null:w.quantity,date:w.date}});
  if(data.side_effect!=='NONE'||data.workflow_unchanged!==true)throw Error('What-if 无副作用契约校验失败');
  state.advancedResponse=data;state.advanced='on';return '隔离 What-if 已计算，原运行与审批状态均未修改';
 }
 case 'recon-reference':case 'recon-dynamic':{
  const data=await request(name==='recon-reference'?'/reconciliation/verified':'/reconciliation/dynamic',{method:'POST',body:{run_id:state.runId,idempotency_key:uuid()}});
  state.advancedResponse=data;state.advanced='on';return '对账结果已从服务器返回；请核对差异状态，而不是假设一致';
 }
 case 'mcp-read':case 'mcp-list':{
  const data=name==='mcp-read'?await request('/mcp/tools/call',{method:'POST',body:{tool:'mrp.get_run',arguments:{run_id:state.runId}}}):await request('/mcp/rpc',{method:'POST',body:{jsonrpc:'2.0',id:1,method:'tools/list',params:{}}});
  state.advancedResponse=data;state.advanced='on';return 'MCP 只读工具响应已返回';
 }
 default:throw Error('UNKNOWN_ACTION');
 }});
}
root.addEventListener('click',e=>{const btn=e.target.closest('button[data-action]');if(!btn||btn.disabled)return;action(btn.dataset.action,btn).catch(err=>{state.message={text:err.message,kind:'error'};render();})});
root.addEventListener('input',e=>{const k=e.target.dataset.bind;if(!k)return;if(k.startsWith('whatif.'))state.whatif[k.split('.')[1]]=e.target.value;else state[k]=e.target.value;});
root.addEventListener('change',e=>{const k=e.target.dataset.bind;if(!k)return;if(k.startsWith('whatif.')){state.whatif[k.split('.')[1]]=e.target.value;render()}else state[k]=e.target.value;});
// Preserve the expand state of the advanced panel without storing credentials.
root.addEventListener('toggle',e=>{if(e.target.id==='vbAdvanced')state.advanced=e.target.open?'on':null},true);
render();
(async()=>{try{const r=await request('/ready',{auth:false,timeout:15000});if(r.status!=='ready'||r.database!=='postgresql')throw Error('PG16 readiness not confirmed');state.ready=true;state.readiness='PostgreSQL 16 · 已就绪';}catch(e){state.ready=false;state.readiness='数据库尚未就绪';state.message={text:'目前无法连接企业数据库：'+e.message+'。其他浏览器模拟页面仍可以独立使用。',kind:'error'}}render()})();
})();
