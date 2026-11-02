'use strict';
const tabs={overview:['经营总览','订单、物料、计划与 AI 决策的统一业务视图'],orders:['销售订单','确认订单与 MTO 业务执行入口'],root:['根订单追溯','读取 PostgreSQL 中已持久化的 MRP 供需分配证据'],materials:['BOM 与库存','物料属性、采购类型与仓库库存快照'],wms:['WMS 库存','PostgreSQL 库存余额、仓库批次与 MRP 计划来源'],mes:['MES 生产执行','工单、工艺路线、产能及执行反馈 · 模拟系统'],mrp:['MRP 计划','全局或指定订单 MRP · 持久化结果与追溯'],agent:['Agent 建议','基于真实 MRP 数据生成的离线受控建议草稿'],workflow:['工作流与审计','状态机、工具调用和 Outbox 事件追踪']};
let rootOrderId='',rootTraceToken=0;
let data=null,tab='overview',chosenWorkflow='',busy=false,selectedRun='',selectedDraft='';
let wmsMaterial='',wmsWarehouse='',wmsOffset=0,wmsPageSize=50,wmsToken=0;
let demoOperatorAvailable=false,demoMRP=null;
let w3Orders=[],w3Selected=new Set(),w3Mode='selected_orders',w3AsOf='2026-11-20',w3OperatorKey='',w3Status=null,w3Submitting=false,w3DetailRequest=0;
const el=id=>document.getElementById(id);
const esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=x=>x==null?'—':esc(x);
const pill=(v)=>{let t=String(v??'—');let type=/COMPLETED|CONFIRMED|ALLOWED|DELIVERED|ACCEPTED/.test(t)?'good':/WAITING|PENDING|GENERATING|CALCULATING/.test(t)?'warn':'neutral';return `<span class="pill ${type}">${esc(t)}</span>`};
const panel=(title,body,extra='')=>`<section class="panel"><div class="panelhead"><h2>${title}</h2>${extra}</div>${body}</section>`;
const table=(headers,rows)=>!rows.length?'<div class="empty">当前数据库暂无记录。请先初始化演示数据或执行工作流。</div>':`<div class="tablewrap"><table><thead><tr>${headers.map(x=>`<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
const tr=cells=>`<tr>${cells.map(c=>`<td>${c}</td>`).join('')}</tr>`;
const kpi=(label,value,hint)=>`<div class="kpi"><div class="accentline"></div><div class="label">${label}</div><div class="value">${esc(value)}</div><div class="hint">${hint}</div></div>`;
const notice=(msg,ok=false)=>{const n=el('notice');n.hidden=!msg;n.className=ok?'alert ok':'alert';n.textContent=msg||''};
async function request(url,options={}){const r=await fetch(url,{headers:{'Content-Type':'application/json'},...options});let json;try{json=await r.json()}catch{throw Error(`HTTP ${r.status}: 非 JSON 响应`)}if(!r.ok)throw Error((json.detail&&json.detail.code)||json.detail?.message||`HTTP ${r.status}`);return json}
async function refresh(force=false){if(busy&&!force)return;el('sync').textContent='正在同步…';try{data=await request('/api/v1/workbench/snapshot');el('sync').textContent=`PostgreSQL · ${new Date().toLocaleTimeString('zh-CN')} 已同步`;notice('');render()}catch(e){data=null;el('sync').textContent='连接失败';el('body').innerHTML='<div class="loading">数据库不可用，无法读取业务数据。请检查 PostgreSQL、迁移与种子数据。</div>';notice('读取失败：'+e.message)}}
function setTab(next){tab=next;if(next==='wms')setTimeout(loadWms,0);if(next==='root')setTimeout(loadRootTrace,0);if(next==='mrp'&&!w3Orders.length)w3LoadOrders();if(next==='mrp')setTimeout(loadDemoMRP,0);document.querySelectorAll('.nav').forEach(n=>n.classList.toggle('active',n.dataset.tab===tab));el('crumb').textContent=tabs[tab][0];el('heading').textContent=tabs[tab][0];el('subtitle').textContent=tabs[tab][1];render()}
function render(){if(!data)return;const d=data;let html='';if(tab==='overview'){
const waiting=d.workflows.filter(w=>w.state==='WAITING_REVIEW').length;
html=`<div class="kpis">${kpi('销售订单',d.orders.length,'ERP · 已持久化')}${kpi('物料主数据',d.materials.length,'ERP · MAKE / BUY')}${kpi('MRP 计算记录',d.runs.length,'PostgreSQL · 历史记录')}${kpi('待审核工作流',waiting,'需人工决策')}</div><div class="cols">${panel('最近销售订单',table(['订单号','产品','数量','交期','状态'],d.orders.slice(0,6).map(o=>tr([esc(o.order_id),esc(o.product_id),esc(o.quantity),esc(o.due_date),pill(o.status)]))))}${panel('执行概况',`<div class="metricrow"><span>工作流总数</span><b>${d.workflows.length}</b></div><div class="metricrow"><span>Agent 建议草稿</span><b>${d.drafts.length}</b></div><div class="metricrow"><span>工具审计事件</span><b>${d.tool_audit.length}</b></div><div class="metricrow"><span>数据来源</span><b>PostgreSQL</b></div>`)}</div>${panel('最近工作流',table(['工作流','订单','状态','版本','MRP Run'],d.workflows.slice(0,8).map(w=>tr([esc(w.workflow_id),esc(w.order_id),pill(w.state),esc(w.version),esc(w.mrp_run_id)]))))}`;
}else if(tab==='orders'){
html=`<div class="note">订单来自 PostgreSQL 的 <b>mock_erp.sales_orders</b>。仅允许为 CONFIRMED 订单创建演示工作流，不修改真实 ERP 订单。</div>${panel('销售订单台账',table(['订单号','产品','订单数量','要求交期','优先级','状态','操作'],d.orders.map(o=>tr([esc(o.order_id),esc(o.product_id),esc(o.quantity),esc(o.due_date),esc(o.priority),pill(o.status),o.status==='CONFIRMED'&&d.write_enabled?`<button class="outline" data-create="${esc(o.order_id)}">创建工作流</button>`:'—']))))}`;
}else if(tab==='root'){
html=panel('根订单 · 真实 PostgreSQL 追溯',`<div class="note">此页面只读取真实持久化结果，不在浏览器重新计算，也不把理论 BOM 需求冒充 MRP 分配。没有记录时会明确提示。</div><div class="toolbar"><label>选择根订单 <select id="rootOrderSelect">${d.orders.map(o=>`<option value="${esc(o.order_id)}" ${o.order_id===rootOrderId?'selected':''}>${esc(o.order_id)} · ${esc(o.product_id)} × ${esc(o.quantity)}</option>`).join('')}</select></label><button class="outline" id="rootReload">读取持久化追溯</button></div><div id="rootTraceResult">正在读取真实 MRP 归因…</div>`);
}else if(tab==='materials'){
html=`<div class="kpis">${kpi('物料数',d.materials.length,'ERP 主数据')}${kpi('采购物料',d.materials.filter(m=>m.make_buy==='BUY').length,'BUY')}${kpi('自制物料',d.materials.filter(m=>m.make_buy==='MAKE').length,'MAKE')}${kpi('库存快照行',d.inventory.length,'WMS')}</div><div class="cols">${panel('物料主数据',table(['物料编号','类型','提前期(天)','单位'],d.materials.map(m=>tr([esc(m.material_id),pill(m.make_buy),esc(m.lead_days),esc(m.uom)]))))}${panel('库存余额',table(['物料','仓库','在库','预留','冻结'],d.inventory.map(m=>tr([esc(m.material_id),esc(m.warehouse_id),esc(m.on_hand),esc(m.reserved),esc(m.blocked)]))))}</div>${panel('生效 BOM 版本与组件',table(['父件','版本','子件','单耗','状态','有效起始'],d.bom.map(b=>tr([esc(b.parent_id),esc(b.version),esc(b.component_id),esc(b.qty_per),pill(b.status),esc(b.valid_from)]))))}<div class="note">BOM 来源为已持久化的生效版本表，可在 MRP 详情查看已持久化的 BOM 父子需求血缘。</div>`;
}else if(tab==='wms'){
html=panel('WMS 库存余额 · PostgreSQL 只读',`<div class="note">库存是当前余额快照，不代表历史 ATP、实际预留或出库。筛选后查询真实 WMS API；来源字段保留仓库与批次。</div><div class="toolbar"><label>物料 <input id="wmsMaterial" placeholder="全部物料" value="${esc(wmsMaterial)}"></label><label>仓库 <input id="wmsWarehouse" placeholder="全部仓库" value="${esc(wmsWarehouse)}"></label><button class="outline" id="wmsSearch">查询库存</button><button class="outline" id="wmsReset">重置</button></div><div id="wmsResults" role="status" aria-live="polite">正在读取库存…</div><div class="toolbar"><button class="outline" id="wmsPrev">上一页</button><span id="wmsPage"></span><button class="outline" id="wmsNext">下一页</button></div>`);
}else if(tab==='mes'){
html=panel('MES 生产工单 · PostgreSQL',`<div class="note">V1.3 模拟 MES：只读查看工单及执行进度。导入 MRP、状态流转与反馈需显式授权；不执行真实生产或库存扣减。</div><div id="mesResults">正在加载 MES 数据…</div>`);
}else if(tab==='mrp'){
html=`${demoMRPPanel()}${demoOperatorAvailable?w3MRPPanel(d):'<div class="note">公共只读环境：真实 MRP 执行仅在创建者隔离测试环境授权开放。</div>'}${panel('MRP 运行记录',table(['运行 ID','状态','快照日期','计算溯源'],d.runs.map(r=>tr([esc(r.run_id),pill(r.status),esc(r.snapshot_as_of),`<button class="outline" data-run="${esc(r.run_id)}">查看计算详情</button>`]))))}<div id="mrpDetail"></div><div class="note">原有工作流 MRP 入口保持不变；V1.1 指定订单计算需显式操作员授权。</div>`;
}else if(tab==='agent'){
html=`<div class="note">当前建议由 <b>offline-contract-v1</b> 确定性模型生成，不是在线大语言模型。建议不会自动生成 ERP 采购申请，必须人工审核。</div>${panel('采购建议草稿',table(['草稿 ID','关联工作流','MRP Run','模型','状态','查看'],d.drafts.map(r=>tr([esc(r.draft_id),esc(r.workflow_id),esc(r.mrp_run_id),esc(r.model_id),pill(r.status),`<button class="outline" data-draft="${esc(r.draft_id)}">查看明细</button>`]))))}<div id="draftDetail"></div>`;
}else if(tab==='workflow'){
let selected=d.workflows.find(w=>w.workflow_id===chosenWorkflow)||d.workflows[0];if(selected)chosenWorkflow=selected.workflow_id;
const options=d.workflows.map(w=>`<option value="${esc(w.workflow_id)}" ${w.workflow_id===chosenWorkflow?'selected':''}>${esc(w.order_id)} · ${esc(w.workflow_id.slice(0,17))} · ${esc(w.state)}</option>`).join('');
const actionable=d.write_enabled&&['CREATED','VALIDATING','CALCULATING','GENERATING_ADVICE'].includes(selected?.state);
html=`<div class="note">工作流动作均为显式教学演示操作，保留版本校验、幂等和 PostgreSQL 审计。VALIDATION_PASSED 为操作员演示确认，不代表真实 ERP 外部校验。<b>WAITING_REVIEW 不提供自动审批。</b></div><div class="toolbar"><select id="workflowSelect" aria-label="选择工作流">${options||'<option>暂无工作流</option>'}</select><button class="primary" id="advance" ${actionable?'':'disabled'}>执行下一步</button><span class="sync">${selected?`当前状态 ${esc(selected.state)} · v${selected.version}`:'请先从订单页面创建工作流'}</span></div>${panel('工作流状态',selected?`<div class="metricrow"><span>工作流 ID</span><b>${esc(selected.workflow_id)}</b></div><div class="metricrow"><span>订单</span><b>${esc(selected.order_id)}</b></div><div class="metricrow"><span>当前状态</span><b>${pill(selected.state)}</b></div><div class="metricrow"><span>MRP Run</span><b>${esc(selected.mrp_run_id)}</b></div>`:'<div class="empty">尚未创建工作流</div>')}<div class="flowsteps">${['CREATED','VALIDATING','CALCULATING','GENERATING_ADVICE','WAITING_REVIEW'].map((state,i)=>`<div class="flowstep ${selected&&(['CREATED','VALIDATING','CALCULATING','GENERATING_ADVICE','WAITING_REVIEW'].indexOf(selected.state)>=i)?'done':''}"><span>${i+1}</span>${state}</div>`).join('')}</div><div id="history"></div><div id="outboxSummary"></div>${panel('最近工具调用审计',table(['时间','工作流','工具','结果','原因','策略版本'],d.tool_audit.slice(0,30).map(a=>tr([esc(a.created_at),esc(a.workflow_id),esc(a.tool_name),pill(a.outcome),esc(a.reason_code),esc(a.policy_version)]))))}`;
}
el('body').innerHTML=html;bind();if(tab==='mrp'&&selectedRun)loadMrp(selectedRun);if(tab==='agent'&&selectedDraft)showDraft(selectedDraft);if(tab==='mes')loadMes();}
function bind(){bindW3();bindWms();bindRootTrace();document.querySelectorAll('[data-create]').forEach(b=>b.onclick=()=>act(async()=>{let w=await request('/api/v1/workbench/workflows',{method:'POST',body:JSON.stringify({order_id:b.dataset.create})});chosenWorkflow=w.workflow_id;tab='workflow';await refresh(true);setTab('workflow')},'工作流创建成功'));
document.querySelectorAll('[data-draft]').forEach(b=>b.onclick=()=>{selectedDraft=b.dataset.draft;showDraft(selectedDraft)});
document.querySelectorAll('[data-run]').forEach(b=>b.onclick=()=>{selectedRun=b.dataset.run;loadMrp(selectedRun)});const sel=el('workflowSelect');if(sel)sel.onchange=()=>{chosenWorkflow=sel.value;render()};const btn=el('advance');if(btn)btn.onclick=()=>{const w=data.workflows.find(x=>x.workflow_id===chosenWorkflow);if(w)act(async()=>{await request('/api/v1/workbench/workflows/'+encodeURIComponent(w.workflow_id)+'/advance',{method:'POST',body:JSON.stringify({expected_version:w.version,as_of:'2026-11-20'})});await refresh(true)},'工作流已推进')};if(tab==='workflow'&&chosenWorkflow)loadHistory(chosenWorkflow);if(tab==='workflow')loadOutboxSummary()}
async function loadHistory(wid){const target=el('history');if(!target)return;try{const h=await request('/api/v1/workbench/workflows/'+encodeURIComponent(wid)+'/history');if(chosenWorkflow!==wid)return;target.innerHTML=panel('状态变更审计',table(['事件','原状态','新状态','版本'],h.transitions.map(x=>tr([esc(x.event_id),esc(x.from_state),pill(x.to_state),esc(x.version)]))))+panel('Outbox 投递状态',table(['消息 ID','事件','主题','状态','尝试次数','投递时间','最后错误'],h.outbox.map(x=>tr([esc(x.message_id),esc(x.event_id),esc(x.topic),pill(x.status),esc(x.attempts),esc(x.delivered_at),esc(x.last_error)]))))}catch(e){target.innerHTML=`<div class="alert">审计查询失败：${esc(e.message)}</div>`}}
async function act(fn,success){if(busy)return;busy=true;try{await fn();notice(success,true)}catch(e){notice('操作失败：'+e.message)}finally{busy=false}}

const num=v=>{let n=Number(v);return Number.isFinite(n)?n.toLocaleString('zh-CN',{maximumFractionDigits:4}):fmt(v)};
async function loadMrp(runId){const token=++w3DetailRequest;const target=el('mrpDetail');if(!target)return;target.innerHTML='<div class="loading">正在读取 PostgreSQL MRP 明细…</div>';try{
const d=await request('/api/v1/workbench/mrp/'+encodeURIComponent(runId)+'/details');if(selectedRun!==runId||tab!=='mrp'||token!==w3DetailRequest)return;
const lines=table(['物料','MAKE/BUY','需求日期','毛需求','净需求','计划数量','期末结余'],d.lines.map(r=>tr([esc(r.material_id),pill(r.make_buy),esc(r.need_date),num(r.gross),num(r.net),num(r.planned),num(r.projected_balance)])));
const attribution=r=>r.root_order_id?esc(r.root_order_id):'<span class="w3-muted" title="持久化记录未提供根订单，不自动推断">未归属（原始为空）</span>';
const provenanceRows=d.provenance||[];
const provenance=table(['物料','根订单归属','需求日','供给类型','已分配数量'],provenanceRows.map(r=>tr([esc(r.material_id),attribution(r),esc(r.need_date),pill(r.supply_kind),num(r.allocated_qty)])));
const linked=provenanceRows.filter(r=>r.root_order_id).length;
const unlinked=provenanceRows.length-linked;
const evidence=`<div class="w3-evidence"><div><small>运行 ID</small><strong>${esc(runId)}</strong></div><div><small>运行状态</small>${pill(d.run.status)}</div><div><small>计算范围</small><strong>${d.order_scope?'指定订单':'全局已确认订单'}</strong></div><div><small>订单 ID</small><strong>${d.order_scope?esc((d.order_scope.order_ids||[]).join(', ')):'全局模式 · 无单订单归属'}</strong></div><div><small>快照日期</small><strong>${esc(d.run.snapshot_as_of)}</strong></div><div><small>规则版本</small><strong>${esc(d.run.rule_version)}</strong></div><div class="w3-wide"><small>Input Hash</small><code>${esc(d.run.input_hash)}</code></div><div class="w3-wide"><small>Result Hash</small><code>${esc(d.run.result_hash)}</code></div></div>`;
const alloc=table(['物料','根订单','供给 ID','分配量','父计划','BOM 版本'],d.allocations.map(r=>tr([esc(r.material_id),attribution(r),esc(r.supply_id),num(r.allocated_qty),esc(r.parent_plan_id),esc(r.bom_version)])));
const bom=table(['父件','子件','BOM 版本','需求日期','子件毛需求'],d.bom_edges.map(r=>tr([esc(r.parent_material),esc(r.child_material),esc(r.bom_version),esc(r.child_need_date),num(r.child_gross_qty)])));
const wmsRows=d.wms_stock_attribution||[];
const wmsEvidence=table(['物料','根订单','仓库','批次','计划归属量','库存版本','库存快照'],wmsRows.map(r=>tr([esc(r.material_id),esc(r.root_order_id??'未归属'),esc(r.warehouse_id),esc(r.lot_id||'无批次'),num(r.allocated_qty),esc(r.source_version),esc(r.source_snapshot_at)])));
const wmsSection=panel('WMS 库存来源 · 计划归属证据',`<div class="note">${d.wms_attribution_contract?`契约 ${esc(d.wms_attribution_contract)} · 仅为模拟计划归属，不是 WMS 实际预留、拣货或跨仓可达性证明。`:'此运行无 V1.2 WMS 计划来源证据（历史运行保持原样，不反推仓库或批次）。'}</div>${wmsEvidence}`);
const supply=table(['物料','供给类型','来源系统','来源单据','供给量','已分配','剩余'],d.supplies.map(r=>tr([esc(r.material_id),pill(r.supply_kind),esc(r.source_system),esc(r.source_document_id),num(r.capacity_qty),num(r.allocated_qty),num(r.remaining_qty)])));
target.innerHTML=`${panel('计算证据 · 持久化运行',`<div class="note">以下证据读取自 PostgreSQL，浏览器不重新计算；Hash 仅用于结果一致性核验，不等于独立审计认证。</div>${evidence}`)}${panel('物料需求与净额计算',lines)}${panel('需求归因 · 持久化订单与供给分配',`<div class="note">来源：platform.mrp_demand_allocations JOIN mrp_supply_sources。展示的是已分配供给量，并非订单毛需求。根订单已关联 ${linked} 行，未归属 ${unlinked} 行；未归属记录保留数据库原值，不推断为当前选中订单。STOCK / RECEIPT / PLAN 分开统计。${d.legacy_pegs_available?'旧版 requirement_pegs 也有数据。':'当前运行使用规范化 M2 归因表。'}</div>`+provenance)}${panel('供需分配明细 · 多订单共享供给',alloc)}${panel('BOM 展开 · 父子需求血缘',bom)}${panel('供给来源与余额',supply)}${wmsSection}`;
}catch(e){target.innerHTML='<div class="alert">MRP 明细读取失败：'+esc(e.message)+'</div>'}}
function showDraft(id){let r=data?.drafts.find(x=>String(x.draft_id)===String(id));const target=el('draftDetail');if(!r||!target)return;let raw=r.draft||{},lines=Array.isArray(raw.lines)?raw.lines:[];
let view=table(['物料','建议数量','建议依据'],lines.map(x=>tr([esc(x.material??x.material_id),num(x.quantity??x.qty),esc(x.reason)])));
target.innerHTML=`<div class="note"><b>草稿 #${esc(r.draft_id)}</b> · ${pill(r.status)} · 工作流 ${esc(r.workflow_id)} · MRP ${esc(r.mrp_run_id)}。当前由 ${esc(r.model_id)} 确定性规则生成；全局 MRP 采购需求不得直接归属单张订单。WAITING_REVIEW 不提供自动审批，也不会写入 ERP。</div>${panel('采购建议 · 人工审核视图',view)}<details class="raw"><summary>查看原始 JSON · 技术核查</summary><pre class="json">${esc(JSON.stringify(raw,null,2))}</pre></details>`}
async function loadOutboxSummary(){let target=el('outboxSummary');if(!target)return;try{let d=await request('/api/v1/workbench/outbox/summary');if(tab!=='workflow')return;target.innerHTML=panel('Outbox 全局投递概况',`<div class="note"><b>PENDING 不等于已投递。</b> 当前 Web 服务不自动启动 Worker，避免隐式推进业务工作流；投递由独立 Worker 显式执行。失败重试/死信状态均从 PostgreSQL 读取。</div><div class="statuscards">${d.counts.map(c=>`<div class="statuscard"><b>${esc(c.status)}</b><strong>${esc(c.count)}</strong></div>`).join('')}</div>`)}catch(e){target.innerHTML='<div class="alert">Outbox 状态读取失败：'+esc(e.message)+'</div>'}}

// V1.2 Batch B: read-only WMS view, no browser-side inventory calculation.
function bindWms(){if(tab!=='wms')return;
const query=()=>{wmsMaterial=el('wmsMaterial').value.trim();wmsWarehouse=el('wmsWarehouse').value.trim();wmsOffset=0;loadWms()};
const search=el('wmsSearch');if(search)search.onclick=query;
const reset=el('wmsReset');if(reset)reset.onclick=()=>{wmsMaterial='';wmsWarehouse='';wmsOffset=0;render();loadWms()};
const prev=el('wmsPrev');if(prev)prev.onclick=()=>{wmsOffset=Math.max(0,wmsOffset-wmsPageSize);loadWms()};
const next=el('wmsNext');if(next)next.onclick=()=>{wmsOffset+=wmsPageSize;loadWms()};
}
async function loadWms(){if(tab!=='wms')return;const token=++wmsToken;
const target=el('wmsResults');if(!target)return;target.textContent='正在读取 PostgreSQL WMS 库存…';
const q=new URLSearchParams({limit:String(wmsPageSize),offset:String(wmsOffset)});
if(wmsMaterial)q.set('material_id',wmsMaterial);if(wmsWarehouse)q.set('warehouse_id',wmsWarehouse);
try{const rows=await request('/api/v1/wms/inventory-balances?'+q.toString());if(token!==wmsToken||tab!=='wms')return;
const headers=['物料','仓库','批次','在手','预留','冻结','可用','快照时间','版本'];
target.innerHTML=table(headers,rows.map(r=>tr([esc(r.material_id),esc(r.warehouse_id),esc(r.lot_id||'无批次'),num(r.on_hand),num(r.reserved),num(r.blocked),num(r.available),esc(r.snapshot_at),esc(r.version)])));
const page=el('wmsPage');if(page)page.textContent=`第 ${Math.floor(wmsOffset/wmsPageSize)+1} 页 · 本页 ${rows.length} 条`;
const prev=el('wmsPrev'),next=el('wmsNext');if(prev)prev.disabled=wmsOffset===0;if(next)next.disabled=rows.length<wmsPageSize;
}catch(e){if(token!==wmsToken)return;target.innerHTML='<div class="alert">WMS 数据读取失败：'+esc(e.message)+'</div>';}}

// W3-02B: the picker reads the V1.1 read-only ERP API; no client-side MRP calculation.
function demoMRPPanel(){return panel('V1.8 Portfolio Demo Extension · EM-100 黄金样例',`<div class="note">独立教学计算 · 不读取线上库存 · 不写 PostgreSQL · 非持久化 MRP Run · Pegging 为单订单需求关联示意，并非 platform.mrp_demand_allocations 数据库证据。</div><button class="primary" id="demoMRPLoad">查看 MRP 演示结果（无需密钥）</button><div id="demoMRPResult" role="status" aria-live="polite">${demoMRP?renderDemoMRP(demoMRP):'点击查看可复现的黄金样例计算结果。'}</div>`)}
function renderDemoMRP(d){const s=d.scenario;const rows=d.result.lines;const bom=table(['父件','子件','单耗'],s.bom.map(x=>tr([esc(x.parent),esc(x.component),esc(x.qty_per)])));const needs=table(['物料','制造/采购','毛需求','可用库存','及时到货','净需求','计划量','需求日','释放日'],rows.map(x=>tr([esc(x.material_id),esc(x.kind),num(x.gross),num(x.available),num(x.timely_receipts),num(x.net),num(x.planned),esc(x.need_date),esc(x.release_date)])));const pegs=table(['根订单','物料','毛需求','计划量','关联类型'],d.pegging_illustration.map(x=>tr([esc(x.root_order_id),esc(x.material_id),num(x.gross),num(x.planned),esc(x.evidence_type)])));const buys=table(['采购物料','建议数量','需求日','释放日'],d.procurement_suggestions.map(x=>tr([esc(x.material_id),num(x.planned),esc(x.need_date),esc(x.release_date)])));return `<div class="note">${esc(s.order_id)} · ${esc(s.product_id)} × ${esc(s.order_quantity)} · 交期 ${esc(s.due_date)} · 教学模拟 · 采购金额（已定义单价部分）¥${esc(d.result.purchase_amount_cny)}</div>${panel('BOM 多级展开',bom)}${panel('库存净需求与批量约束',needs)}${panel('Pegging · 单订单需求关联示意',pegs)}${panel('采购建议',buys)}${panel('可复现计算快照',`<div class="metricrow"><span>规则版本</span><b>${esc(d.snapshot.rule_version)}</b></div><div class="metricrow"><span>SHA-256</span><code style="overflow-wrap:anywhere">${esc(d.snapshot.fingerprint_sha256)}</code></div><div class="note">本快照由内存中确定性算法生成，未持久化，不存在数据库 Run ID；不得冒充实时库存、实际采购单或已落库 Pegging。</div>`)}`}
async function loadDemoMRP(){if(tab!=='mrp')return;const btn=el('demoMRPLoad');if(btn)btn.onclick=loadDemoMRP;const target=el('demoMRPResult');if(!target)return;target.textContent='正在计算黄金样例…';try{const [cap,d]=await Promise.all([request('/api/v1/portfolio-demo/capabilities'),request('/api/v1/portfolio-demo/mrp/golden')]);demoOperatorAvailable=cap.operator_execution_available;demoMRP=d;if(tab==='mrp'){render();const out=el('demoMRPResult');if(out)out.innerHTML=renderDemoMRP(d)}}catch(e){if(target)target.textContent='演示读取失败：'+e.message}}
function w3MRPPanel(d){
const rows=w3Orders.filter(o=>o.status==='CONFIRMED');
const options=rows.map(o=>`<label class="w3-order"><input type="checkbox" data-w3-order="${esc(o.order_id)}" ${w3Selected.has(o.order_id)?'checked':''} ${w3Mode==='global'?'disabled':''}> <b>${esc(o.order_id)}</b> · ${esc(o.due_date)} · ${esc(o.lines.map(l=>l.product_id+' × '+l.quantity).join(', '))}</label>`).join('');
return panel('V1.1 · 订单驱动 MRP',`<div class="note">ERP 订单只读；MRP 运行会在隔离数据库持久化结果。必须显式启用写入并提供操作员密钥。公共演示环境禁止执行。</div><div class="w3-form"><label>计算范围 <select id="w3Mode"><option value="selected_orders" ${w3Mode==='selected_orders'?'selected':''}>指定订单</option><option value="global" ${w3Mode==='global'?'selected':''}>全局已确认订单（V1.0 兼容）</option></select></label><label>快照日期 <input id="w3AsOf" type="date" value="${esc(w3AsOf)}"></label><label>操作员密钥（仅本次页面会话） <input id="w3Key" type="password" autocomplete="off" placeholder="执行时需要"></label><div class="w3-orders">${options||'正在加载 ERP 订单或暂无已确认订单'}</div><div class="w3-actions"><button class="outline" id="w3LoadOrders">刷新 ERP 订单</button> <button class="primary" id="w3Execute" ${w3Submitting?'disabled':''}>${w3Submitting?'MRP 计算中…':'执行 MRP 并保存结果'}</button></div><div id="w3Status" class="w3-status ${w3Status?.kind||''}" role="status" aria-live="polite" ${w3Status?'':'hidden'}>${w3Status?esc(w3Status.message):''}</div></div>`);
}
async function w3LoadOrders(){try{const rows=await request('/api/v1/erp/sales-orders?status=CONFIRMED&limit=100');w3Orders=rows;w3Selected=new Set([...w3Selected].filter(x=>rows.some(o=>o.order_id===x)));if(tab==='mrp')render()}catch(e){notice('ERP 订单读取失败：'+e.message)}}
function bindW3(){if(tab!=='mrp')return;
const demoButton=el('demoMRPLoad');if(demoButton)demoButton.onclick=loadDemoMRP;const mode=el('w3Mode');if(!mode)return;mode.onchange=()=>{w3Mode=mode.value;render()};
const asOf=el('w3AsOf');if(asOf)asOf.onchange=()=>{w3AsOf=asOf.value};
const key=el('w3Key');if(key){key.value=w3OperatorKey;key.oninput=()=>{w3OperatorKey=key.value}};
document.querySelectorAll('[data-w3-order]').forEach(c=>c.onchange=()=>{if(c.checked)w3Selected.add(c.dataset.w3Order);else w3Selected.delete(c.dataset.w3Order)});
const load=el('w3LoadOrders');if(load)load.onclick=()=>w3LoadOrders();
const go=el('w3Execute');if(go)go.onclick=async()=>{
if(w3Submitting)return;
const setStatus=(kind,message)=>{w3Status={kind,message};const status=el('w3Status');if(status){status.hidden=false;status.className='w3-status '+kind;status.textContent=message}};
if(w3Mode==='selected_orders'&&w3Selected.size===0){setStatus('error','请选择至少一张已确认订单');return}
if(!w3OperatorKey){setStatus('error','请输入操作员密钥');return}
if(!/^\d{4}-\d{2}-\d{2}$/.test(w3AsOf)){setStatus('error','请选择有效的快照日期');return}
w3Submitting=true;go.disabled=true;go.textContent='MRP 计算中…';setStatus('pending','请求已发送，请勿重复点击。正在等待计算及持久化结果…');
try{
const body={as_of:w3AsOf,order_scope:{mode:w3Mode,order_ids:w3Mode==='global'?[]:[...w3Selected].sort()}};
const r=await request('/api/v1/workbench/mrp/runs',{method:'POST',headers:{'Content-Type':'application/json','X-Operator-Key':w3OperatorKey},body:JSON.stringify(body)});
selectedRun=r.run_id;setStatus('success','MRP 已持久化 · Run ID: '+r.run_id);
await refresh(true);
// refresh() re-renders the panel; restore the local status next to the action.
const status=el('w3Status');if(status){status.hidden=false;status.className='w3-status success';status.textContent=w3Status.message}
const detail=el('mrpDetail');if(detail){detail.scrollIntoView({behavior:'smooth',block:'start'});}
}catch(e){setStatus('error','MRP 执行失败：'+e.message+'。请核查后端日志，确认未生成运行记录后再重试。')}
finally{w3Submitting=false;const button=el('w3Execute');if(button){button.disabled=false;button.textContent='执行 MRP 并保存结果'}}
};}
document.querySelectorAll('.nav').forEach(n=>n.onclick=()=>setTab(n.dataset.tab));el('refresh').onclick=()=>refresh();refresh();

// V1.3 MES readback; all values escaped before rendering.
async function loadMes(){const target=el('mesResults');if(!target||tab!=='mes')return;try{
const rows=await request('/api/v1/mes/work-orders');if(tab!=='mes')return;
const summary=table(['工单','MRP 来源','计划 ID','物料','计划量','交期','状态','版本','查看'],rows.map(r=>tr([esc(r.work_order_id),esc(r.source_run_id),esc(r.source_plan_id),esc(r.product_id),num(r.quantity),esc(r.due_date),pill(r.status),esc(r.revision),`<button class="outline" data-mes-order="${esc(r.work_order_id)}">查看执行证据</button>`])));
target.innerHTML=summary+'<div id="mesDetails"></div>';document.querySelectorAll('[data-mes-order]').forEach(b=>b.onclick=()=>loadMesDetail(b.dataset.mesOrder));
}catch(e){target.innerHTML='<div class="alert">MES 数据读取失败：'+esc(e.message)+'</div>'}}
async function loadMesDetail(id){const target=el('mesDetails');if(!target)return;try{const d=await request('/api/v1/mes/work-orders/'+encodeURIComponent(id));
target.innerHTML=panel('工单执行证据',`<div class="note">工单 ${esc(id)} · 状态 ${pill(d.progress.status)} · 已完成良品 ${num(d.progress.finished_good_qty)} · 剩余 ${num(d.progress.remaining_qty)} · 事件 ${num(d.progress.feedback_events)}。不代表真实设备反馈。</div>`+table(['工序','工作中心','标准工时/件','准备工时'],d.routing.map(x=>tr([esc(x.operation_id),esc(x.work_center),num(x.hours_per_unit),num(x.setup_hours)])))+table(['事件','工序','良品','报废','日期'],d.events.map(x=>tr([esc(x.event_id),esc(x.operation_id),num(x.good_qty),num(x.scrap_qty),esc(x.event_date)]))));
}catch(e){target.innerHTML='<div class="alert">MES 详情读取失败：'+esc(e.message)+'</div>'}}


// RC4 root-order integration: no offline mock, no fallback to seed data.
function bindRootTrace(){
 if(tab!=='root')return;
 const select=el('rootOrderSelect');
 if(select){if(!rootOrderId||![...select.options].some(o=>o.value===rootOrderId))rootOrderId=select.value;
   select.value=rootOrderId;
   select.onchange=()=>{rootOrderId=select.value;loadRootTrace()};}
 const reload=el('rootReload');if(reload)reload.onclick=()=>loadRootTrace();
}
async function loadRootTrace(){
 if(tab!=='root')return;
 const select=el('rootOrderSelect'),target=el('rootTraceResult');if(!target)return;
 const id=select?.value||rootOrderId;
 if(!id){target.textContent='当前 PostgreSQL 没有可选择的根订单。';return}
 rootOrderId=id;const token=++rootTraceToken;
 target.textContent='正在查询 PostgreSQL 已持久化的根订单归因…';
 try{
  const d=await request('/api/v1/workbench/root-orders/'+encodeURIComponent(id)+'/trace');
  if(tab!=='root'||token!==rootTraceToken)return;
  const o=d.order;
  const summary=panel('根订单信息',`<div class="metricrow"><span>订单</span><b>${esc(o.order_id)}</b></div><div class="metricrow"><span>产品与数量</span><b>${esc(o.product_id)} × ${esc(o.quantity)}</b></div><div class="metricrow"><span>交期</span><b>${esc(o.due_date)}</b></div><div class="metricrow"><span>状态</span><b>${pill(o.status)}</b></div>`);
  const runs=panel('关联 MRP 运行 · 数据库证据',table(['运行 ID','状态','快照日期','输入 Hash','结果 Hash','详情'],d.runs.map(r=>tr([esc(r.run_id),pill(r.status),esc(r.snapshot_as_of),esc(r.input_hash),esc(r.result_hash),`<button class="outline" data-root-run="${esc(r.run_id)}">查看 MRP 明细</button>`]))));
  const rows=panel('根订单供需分配 · Pegging',table(['MRP Run','物料','需求日期','供给 ID','已分配量','父计划','BOM 版本'],d.allocations.map(a=>tr([esc(a.run_id),esc(a.material_id),esc(a.need_date),esc(a.supply_id),esc(a.allocated_qty),esc(a.parent_plan_id),esc(a.bom_version)]))));
  const empty=d.evidence_status==='NO_PERSISTED_ALLOCATION'?'<div class="note">此订单当前没有已持久化的供需分配记录。请在隔离写入环境运行 MRP 并完成持久化；公共只读演示不自动生成数据。</div>':'';
  target.innerHTML=summary+empty+runs+rows;
  target.querySelectorAll('[data-root-run]').forEach(b=>b.onclick=()=>{selectedRun=b.dataset.rootRun;setTab('mrp');const detail=el('mrpDetail');if(detail)detail.textContent="请在 MRP 运行记录中查看此运行的计算详情。";});
 }catch(e){if(token===rootTraceToken)target.innerHTML='<div class="alert">根订单真实数据读取失败：'+esc(e.message)+'</div>'}
}
