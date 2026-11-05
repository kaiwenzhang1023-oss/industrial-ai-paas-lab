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
const state={scenario:'A',snapshot:null,ready:false,readiness:'检查 PostgreSQL 连接中',session:null,token:'',runId:'',commandId:'',run:null,overview:null,command:null,workflow:null,view:'mrp',busy:false,message:null,reason:'MRP物料计划已核对，批准进入内部执行流程',runInput:'',lineSearch:'',linePage:1,lineKind:'requirements',whatif:{kind:'stock',target:'BR-01',quantity:'80',date:'2026-11-20'},advanced:null,advancedResponse:null,raw:null, lastWorker:null};
const root=document.createElement('section');root.id='vbConsole';root.hidden=true;root.setAttribute('aria-label','Version B 企业级运行闭环工作台');
main.appendChild(root);
const button=document.createElement('button');button.id='vbConsoleNav';button.className='nav';button.type='button';button.textContent='▣ MRP 企业执行中心';button.setAttribute('aria-controls','vbConsole');
// Version B is the primary product. Keep the browser-only simulation as an explicitly secondary workspace.
const enterpriseLabel=document.createElement('div');enterpriseLabel.className='nav-group vbc-nav-label';enterpriseLabel.textContent='企业业务 · 审批与执行';
nav.insertBefore(button,nav.firstChild);
nav.insertBefore(enterpriseLabel,button);
const simulationLabel=nav.querySelector('.nav-group:not(.vbc-nav-label)');
if(simulationLabel)simulationLabel.textContent='浏览器模拟 · 辅助演示';
let showing=false;
function activate(){showing=true;document.body.classList.add('vbc-body-active');main.classList.add('vbc-active');root.hidden=false;document.querySelectorAll('#nav .nav').forEach(x=>x.classList.toggle('active',x===button));document.getElementById('crumb').textContent='企业执行中心 · Version B';document.body.classList.remove('sidebar-open');button.setAttribute('aria-current','page');render();}
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
function canExecute(){return hasRun()&&status()==='APPROVED_QUEUED'&&decision()?.type==='APPROVED'&&!!(state.commandId||command()?.command_id)&&!['DONE','DEAD'].includes(command()?.status)}
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
const businessStatus={NO_RUN:'尚未生成计划',WAITING_REVIEW:'待人工审核',APPROVED_QUEUED:'审批通过，待执行校验',EXECUTED_INTERNAL:'内部校验已完成',REJECTED:'申请已驳回',DONE:'内部校验已完成',DEAD:'执行失败，请联系管理员',FAILED_TERMINAL:'执行失败',PENDING:'待执行',RUNNING:'校验进行中',RETRY_PENDING:'等待重试'};
function friendly(v){return businessStatus[v]||({'APPROVED':'已批准','REJECTED':'已驳回','CLAIMED':'正在处理','READ_SUCCESS':'读取成功'}[v]||'状态待确认')}
function flowNext(){if(!isReady())return '请先开始访客演示';if(!hasRun())return '下一步：生成 MRP 计划单';if(isReviewable())return '下一步：核对物料需求并完成审批';if(status()==='REJECTED')return '计划已驳回，可新建下一张计划单';if(canExecute())return '下一步：执行内部业务校验';if(command()?.status==='DONE'||status()==='EXECUTED_INTERNAL')return '流程已完成，请查看执行回执和审计记录';return '请刷新审批及执行状态，确认下一步';}
function businessBadge(v){return `<span class="vbc-chip ${tone(v)}" aria-label="当前业务状态">${E(friendly(v))}</span>`}
function businessCard(title,body){return `<section class="vbc-business-card"><h2>${E(title)}</h2>${body}</section>`}
function businessTimeline(){const events=state.overview?.events||state.workflow?.events||[];const names={APPROVED:'审批通过',REJECTED:'审批驳回',WORKER_EXECUTED_INTERNAL:'后台完成内部业务校验',WORKER_DONE:'后台完成内部业务校验',EXECUTED_INTERNAL:'内部业务校验完成'};const items=[];if(state.run)items.push({title:'生成 MRP 计划单',at:state.run?.created_at||state.run?.createdAt||null,source:'当前单据详情',kind:'run'});for(const ev of events){items.push({title:names[ev.action]||'业务审计事件',at:ev.at,source:'数据库审计事件',kind:'audit',details:ev.action,actor:ev.actor});}if(command()?.receipt)items.push({title:'执行回执已生成',at:command()?.receipt?.processed_at||command()?.receipt?.at||null,source:'数据库执行回执',kind:'receipt'});return items.length?`<ol class="vbc-business-timeline">${items.map(x=>`<li><strong>${E(x.title)}</strong><span>${E(x.at?formatTime(x.at):'时间未由接口提供')} · ${E(x.source)}</span>${x.actor?`<small>操作人：${E(x.actor)}</small>`:''}</li>`).join('')}</ol>`:empty('尚无流程记录','生成计划单后，审批与执行记录将在这里按时间展示。');}
function businessPage(){const dec=decision(),cmd=command(),receipt=cmd?.receipt,lines=state.run?.lines||[],pegs=state.run?.pegs||[];const gross=lines.reduce((n,x)=>n+(Number(x.gross)||0),0),net=lines.reduce((n,x)=>n+(Number(x.net)||0),0),planned=lines.reduce((n,x)=>n+(Number(x.planned)||0),0);const sourceOrders=state.snapshot?.orders||[];const shortageMaterials=new Set(lines.filter(x=>Number(x.net)>0).map(x=>x.material));const purchaseItems=state.snapshot?.items||{};const purchaseSuggestions=lines.filter(x=>Number(x.planned)>0&&purchaseItems[x.material]?.kind==='BUY');const sourceScenario=state.run?.snapshot?.source_versions?.scenario;const ready=isReady(),has=hasRun(),review=isReviewable(),exec=canExecute(),finished=!!receipt&&cmd?.status==='DONE';const statusValue=status();return `
<section class="vbc-business-head"><div><div class="vbc-eyebrow">VERSION B · 企业业务单据演示</div><h1>MRP 企业闭环执行中心</h1><p>从物料计划、人工审批到内部校验、执行回执和审计追溯</p></div><div class="vbc-business-status">${businessBadge(statusValue)}<strong>${E(flowNext())}</strong></div></section>
<details class="vbc-business-guide"><summary>了解演示范围与 Version A / Version B 的区别</summary><p>Version A 及左侧「MRP 计划」为浏览器本地模拟；本页面 Version B 使用企业数据库保存计划单、审批、执行回执与审计记录。两套 MRP 当前不自动同步。</p><p><strong>重要边界：</strong>只进行内部业务逻辑校验，不向 MES、SRM 或真实工厂下发生产、采购指令。演示数据为样例数据。</p></details>
<div class="vbc-session"><div><strong>访客演示会话</strong><p>${ready?'已连接独立演示租户：'+E(state.session.tenant):'尚未建立访客会话'}。业务记录存入数据库；刷新页面会丢失临时身份，需要重新开始会话。请勿把单据编号当作访问凭据。</p></div>${ready?`<button class="vbc-btn tiny" data-action="logout" ${busyAttr()}>退出访客会话</button>`:`<button class="vbc-btn primary" data-action="connect" ${busyAttr(state.ready)}>开始访客演示</button>`}</div>
<div class="vbc-business-overview"><div><span>MRP 计划单编号</span><strong>${E(state.runId||'尚未生成')}</strong></div><div><span>当前状态</span>${businessBadge(statusValue)}</div><div><span>审批结果</span><strong>${E(dec?friendly(dec.type):'尚未审批')}</strong></div><div><span>执行结果</span><strong>${E(cmd?friendly(cmd.status):'尚未执行')}</strong></div></div>
<div class="vbc-business-actions">${businessCard('01 · 计划单操作',`<label class="vbc-field">选择生产业务场景<select data-bind="scenario" ${busyAttr(ready)}><option value="A" ${state.scenario==='A'?'selected':''}>A · 正常生产</option><option value="B" ${state.scenario==='B'?'selected':''}>B · 关键物料短缺</option><option value="C" ${state.scenario==='C'?'selected':''}>C · 客户交期顺延 7 天</option><option value="D" ${state.scenario==='D'?'selected':''}>D · BOM 用量翻倍异常（需人工核对）</option></select></label><p class="vbc-low">四种场景在后端生成不同的计算快照；不会修改其他访客的共享样例源表。D 场景用于演示人工识别与驳回异常。</p><div class="vbc-action-row"><button class="vbc-btn primary" data-action="create" ${busyAttr(ready)}>生成 MRP 计划单</button><button class="vbc-btn" data-action="lookup" ${busyAttr(ready&&!!state.runInput.trim())}>查询计划单</button><button class="vbc-btn" data-action="refresh" ${busyAttr(has)}>刷新单据及状态</button><button class="vbc-btn" data-action="reset-flow" ${busyAttr(ready&&!!state.runId)}>重置当前演示流程</button></div><label class="vbc-field">查询本访客租户的计划单编号<input data-bind="runInput" value="${E(state.runInput||state.runId)}" placeholder="输入 MRP 单据编号"></label><p class="vbc-low">重置仅清空页面选择，不删除数据库历史单据。</p>`)}
${businessCard('02 · 人工审批',`<label class="vbc-field">审批意见模板<select data-action="reason-template" ${busyAttr(review)}><option value="">选择常用审批意见</option><option value="MRP物料计划已核对，批准进入内部执行流程">计划核对通过</option><option value="BOM/库存校验不通过，驳回，请核对物料数据">物料数据需要修正</option></select></label><label class="vbc-field">审批意见<textarea data-bind="reason" maxlength="1000" placeholder="例如：MRP物料计划已核对，批准进入内部执行流程" ${busyAttr(review)}>${E(state.reason)}</textarea></label><div class="vbc-action-row"><button class="vbc-btn teal" data-action="approve" ${busyAttr(review)}>批准计划</button><button class="vbc-btn danger" data-action="reject" ${busyAttr(review)}>驳回计划</button></div>`)}
${businessCard('03 · 执行与回执',`<div class="vbc-action-row"><button class="vbc-btn primary" data-action="dispatch" ${busyAttr(exec)}>执行内部业务校验</button><button class="vbc-btn" data-action="receipt" ${busyAttr(has&&!!(state.commandId||cmd?.command_id))}>查看执行回执单</button><button class="vbc-btn" data-action="refresh" ${busyAttr(has)}>刷新审批与执行状态</button></div><p class="vbc-low">执行仅用于平台内部验证，不会生成外部采购单或生产指令。</p>`)}
${businessCard('04 · 审计查询',`<div class="vbc-action-row"><button class="vbc-btn" data-action="refresh" ${busyAttr(has)}>刷新全流程审计时间线</button></div><p class="vbc-low">时间线只展示真实单据、数据库审计及执行回执数据，不补造事件。</p>`)}</div>
<div class="vbc-business-results">${businessCard('MRP 物料计划摘要',has?`<div class="vbc-business-metrics"><div><span>物料需求明细</span><strong>${lines.length} 行</strong></div><div><span>总净需求量</span><strong>${E(labelNum(net))}</strong></div><div><span>计划供应数量</span><strong>${E(labelNum(planned))}</strong></div><div><span>关联销售订单</span><strong>${sourceOrders.length} 单</strong></div><div><span>缺口物料</span><strong>${shortageMaterials.size} 种</strong></div><div><span>采购建议</span><strong>${purchaseSuggestions.length} 项</strong></div></div><p class="vbc-low">当前场景：${E(sourceScenario?.name||'历史默认场景')}；关联订单：${E(sourceOrders.map(o=>o.order_id).join('、')||'未提供')}。预估采购金额：未提供物料单价，不能推算。<br>上述数值直接汇总当前企业计划单的后端物料需求行；未提供订单总数时不推断订单数量。毛需求合计：${E(labelNum(gross))}。</p><details><summary>查看物料明细及供需追溯</summary>${runTable()}</details>`:empty('等待生成计划单','创建单据后显示当前数据库计算出的物料需求与供应建议。'))}
${businessCard('审批记录',dec?`<div class="vbc-detail-list">${pair('审批结论',friendly(dec.type))}${pair('审批人',dec.actor)}${pair('审批时间',formatTime(dec.at))}${pair('审批意见',dec.reason)}</div>`:empty('尚无审批记录','计划单生成后，由访客进行人工审核。'))}
${businessCard('执行回执单',receipt?`<div class="vbc-detail-list">${pair('执行结果',friendly(cmd.status))}${pair('内部执行类型','仅内部逻辑校验')}${pair('外部工厂指令','未下发')}${pair('执行时间',formatTime(receipt.processed_at||receipt.at))}</div>`:empty('尚未生成回执','审批通过并完成内部校验后，这里会显示数据库回执。'))}
${businessCard('全流程审计时间线',businessTimeline())}</div>
<details class="vbc-technical"><summary>查看原始后端报文与技术核验信息（开发调试用）</summary><div class="vbc-pane-body"><div class="vbc-detail-list">${pair('MRP Run ID',state.runId)}${pair('Command ID',state.commandId||cmd?.command_id)}${pair('原始工作流状态',statusValue)}${pair('原始命令状态',cmd?.status)}${pair('快照指纹',state.overview?.snapshot_hash||state.run?.input_hash)}${pair('数据库就绪',state.readiness)}</div>${state.technicalError?`<details><summary>查看最近一次技术错误</summary><pre>${E(JSON.stringify(state.technicalError,null,2))}</pre></details>`:''}${raw()}${advancedPanel()}</div></details>
<div class="vbc-footer">Version B RC3.4 候选 · 真实企业数据库样例 · 内部业务校验，不连接生产系统 · 技术信息默认折叠</div>`;}
function render(){if(!root)return;const message=state.message?`<div class="vbc-toast ${E(state.message.kind||'')}" role="status">${E(state.message.text)}</div>`:'';root.innerHTML=message+businessPage();}

async function request(path,{method='GET',body=null,auth=true,timeout=30000}={}){
 if(auth&&!state.token)throw new Error('请先建立独立演示会话');
 const ctrl=new AbortController();const timer=setTimeout(()=>ctrl.abort(),timeout);
 let res;
 try{res=await fetch((path==='/ready'||path.startsWith('/api/'))?path:api+path,{method,signal:ctrl.signal,cache:'no-store',headers:{...(auth?{'Authorization':'Bearer '+state.token}:{}),...(body!==null?{'Content-Type':'application/json'}:{})},body:body===null?undefined:JSON.stringify(body)});}catch(e){if(e.name==='AbortError')throw Error('请求超时（30 秒），Render 可能正在唤醒；写入操作结果未知，请刷新状态核实后再决定是否操作');throw Error('网络请求失败：'+e.message);}finally{clearTimeout(timer)}
 let data;try{data=await res.json()}catch{data={detail:'INVALID_JSON_RESPONSE'}}
 if(!res.ok){if(res.status===401){clearSession();}const reasons={401:'访客会话已失效，请重新开始演示',403:'当前访客无权执行此操作',404:'找不到当前访客的计划单',409:'单据状态已变化，无法重复操作，请刷新确认',422:'业务数据不符合计算规则，请检查场景输入',429:'操作过于频繁，请稍后再试',503:'企业服务暂不可用，请稍后重试'};state.technicalError={http_status:res.status,details:data};throw Error(reasons[res.status]||'操作暂时失败，请稍后重试');}
 state.raw={path:(path==='/ready'||path.startsWith('/api/'))?path:api+path,method,data:path.includes('/preview/session')?{status:'SESSION_ISSUED',token_redacted:true}:data};return data;
}
function clearSession(){state.token='';state.session=null;state.runId='';state.runInput='';state.commandId='';state.run=null;state.snapshot=null;state.overview=null;state.command=null;state.workflow=null;state.lastWorker=null;state.advancedResponse=null;state.reason='MRP物料计划已核对，批准进入内部执行流程';try{localStorage.removeItem('v19b_last_run_id')}catch{}}
async function fetchRun(id){
 if(!id)throw Error('请填写 Run ID');
 const data=await request('/mrp/runs/'+encodeURIComponent(id));
 if(data.source!=='postgresql'||!Array.isArray(data.run?.lines)||!Array.isArray(data.run?.pegs))throw Error('MRP_RUN_CONTRACT_MISMATCH');
 // When browsing another MRP within the same tenant, never reuse the prior command or receipt.
 if(state.runId && state.runId!==id){state.commandId='';state.command=null;state.overview=null;state.workflow=null;state.lastWorker=null;state.advancedResponse=null;}
 state.run=data.run;state.snapshot=data.canonical_snapshot;state.runId=id;state.runInput=id;try{localStorage.setItem('v19b_last_run_id',id)}catch{}
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
async function perform(action,handler){if(state.busy)return;state.busy=true;state.message={text:'正在处理业务请求，请稍候…',kind:''};render();try{const result=await handler();state.message={text:result||'操作已完成。结果已从服务器返回。',kind:'success'};}catch(e){state.message={text:e.message||String(e),kind:'error'};}finally{state.busy=false;render();}}
async function action(name,el){
 if(name==='reset-flow'){state.runId='';state.runInput='';state.commandId='';state.run=null;state.snapshot=null;state.overview=null;state.command=null;state.workflow=null;state.lastWorker=null;try{localStorage.removeItem('v19b_last_run_id')}catch{}state.message={text:'已清空当前页面流程，历史单据仍保存在企业数据库。',kind:'success'};render();return;}
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
  return '访客演示会话已建立，现在可以选择业务场景并生成计划单。';
 }
 case 'create':{
  const created=await request('/mrp/runs',{method:'POST',body:{scenario:state.scenario}});if(!created.run_id||created.source!=='postgresql')throw Error('MRP_CREATE_CONTRACT_MISMATCH');
  state.runId=created.run_id;state.runInput=created.run_id;try{localStorage.setItem('v19b_last_run_id',created.run_id)}catch{}state.commandId='';state.command=null;state.overview=null;state.run=null;state.lineSearch='';state.linePage=1;state.lastWorker=null;
  try{await fetchRun(created.run_id);}catch(e){throw Error('MRP 已提交，Run ID='+created.run_id+'；但详情加载失败：'+e.message+'。请使用 Run ID 查询，避免重复创建。')}
  state.view='mrp';return 'MRP 计划单已生成：'+created.run_id+'。请核对物料需求并完成审批。';
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
  if(decided.status!=='ACCEPTED'||(outcome==='APPROVED'&&!decided.command_id))throw Error('审批响应契约不符合预期');
  state.commandId=decided.command_id;await fetchOverview();state.view=outcome==='APPROVED'?'execution':'audit';
  return outcome==='APPROVED'?'审批已保存，Outbox 命令已入队（尚未执行）':'驳回已保存；该运行不会执行 Worker';
 }
 case 'dispatch':{
  if(!canExecute())throw Error('没有可执行的已批准命令');
  const result=await request('/worker/dispatch',{method:'POST'});
  if(result.external_execution!==false)throw Error('WORKER_EXTERNAL_EXECUTION_GUARD');
  state.lastWorker=result;await fetchOverview();if(state.commandId)await fetchCommand();
  return '内部业务校验已提交，当前状态：'+friendly(command()?.status)+'。请查看执行回执。';
 }
 case 'receipt':{await fetchCommand();await fetchOverview();return '执行回执已刷新，请查看业务回执卡片';}
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
root.addEventListener('change',e=>{if(e.target.dataset.action==='reason-template'&&e.target.value){state.reason=e.target.value;render();return;}const k=e.target.dataset.bind;if(!k)return;if(k.startsWith('whatif.')){state.whatif[k.split('.')[1]]=e.target.value;render()}else state[k]=e.target.value;});
// Preserve the expand state of the advanced panel without storing credentials.
root.addEventListener('toggle',e=>{if(e.target.id==='vbAdvanced')state.advanced=e.target.open?'on':null},true);
// Open the actual enterprise workflow on first load; do not strand visitors on the Version A-like simulation.
activate();
nav.scrollTop=0;
(async()=>{try{const r=await request('/ready',{auth:false,timeout:15000});if(r.status!=='ready'||r.database!=='postgresql')throw Error('PG16 readiness not confirmed');state.ready=true;state.readiness='PostgreSQL 16 · 已就绪';}catch(e){state.ready=false;state.readiness='数据库尚未就绪';state.message={text:'企业数据库暂时无法连接，稍后再试。浏览器模拟实验室仍可使用。',kind:'error'}}try{const last=localStorage.getItem('v19b_last_run_id');if(last&&!state.runId){state.runInput=last;state.message={text:'已找回上次计划单编号。为保护租户数据，请重新建立原访客会话后才能查询；新会话不能访问旧租户记录。',kind:''}}}catch{}render()})();
})();
