/* RC4: auditable order-level decision evidence, deterministic and read-only. */
(function(root){'use strict';
const round=n=>Math.round((Number(n)+Number.EPSILON)*1000)/1000;
function build(master,state,result,orderId){
 const m=result.modules, order=m.orders.find(x=>x.id===orderId);if(!order)throw Error('ORDER_NOT_FOUND');
 const peg=m.pegging.filter(x=>x.order_id===orderId);
 const materials=new Set(peg.map(x=>x.material_id));
 const related=x=>x.order_id===orderId||(x.order_id==='MULTI_ORDER'&&materials.has(x.material_id));
 const exceptions=m.exceptions.filter(related), purchases=m.purchase.filter(related);
 const mapping=m.mapping.find(x=>x.order_id===orderId), work=m.workorders.find(x=>x.order_id===orderId);
 const supplierById=new Map(master.suppliers.map(x=>[x.id,x]));
 const rules=[];const add=(id,priority,hit,description,checks,action)=>rules.push({id,priority,hit:!!hit,description,checks,action});
 const blocked=mapping?.status==='BLOCKED_REVIEW';
 add('R-MAP-001',100,blocked,'发布 BOM 版本映射一致性',[
  {field:'mapping.status',actual:mapping?.status||'MISSING',operator:'=',threshold:'BLOCKED_REVIEW',ref:mapping?.mapping_id||'—'},
  {field:'mapping.observed_value',actual:mapping?.observed_value||'—',operator:'≠',threshold:mapping?.expected_value||'—',ref:mapping?.mapping_id||'—'}
 ],'暂停下游采购和生产模拟流转，核对 BOM 版本映射。');
 const overdue=purchases.filter(x=>x.release_date<(master.scenarios[state.scenarioId].as_of||master.metadata.as_of));
 add('R-RELEASE-002',90,overdue.length>0,'计划释放日期早于场景基准日',overdue.slice(0,5).map(x=>({field:'purchase.release_date',actual:x.release_date,operator:'<',threshold:master.scenarios[state.scenarioId].as_of||master.metadata.as_of,ref:x.pr_id})), '先人工重排采购释放日期，禁止将逾期计划当作已执行采购。');
 const supplierRisks=[];for(const x of purchases){const s=supplierById.get(x.supplier_id);if(s&&Number(s.onTimeRate)<0.9)supplierRisks.push({pr:x,s});}
 add('R-SUPPLIER-003',80,supplierRisks.length>0,'供应商准交率低于 90% 阈值',supplierRisks.slice(0,5).map(({pr,s})=>({field:'supplier.onTimeRate',actual:round(s.onTimeRate*100)+'%',operator:'<',threshold:'90%',ref:pr.pr_id+' / '+s.id})), '复核供应商交期承诺，要求人工确认备选供应或交付计划。');
 const delay=Number(work?.forecast_delay_days||0);
 add('R-DELAY-004',70,delay>0,'模拟延期偏移量大于零', [{field:'workorder.forecast_delay_days',actual:delay,operator:'>',threshold:0,ref:work?.work_order_id||'—'}], '复核模拟延期对订单交期的影响；该日期不代表产能排程预测。');
 add('R-PR-005',40,purchases.length>0,'存在关联采购建议', [{field:'purchase.related_count',actual:purchases.length,operator:'>',threshold:0,ref:purchases.slice(0,3).map(x=>x.pr_id).join(', ')||'—'}], '根据物料缺口、需求日期和释放日期复核采购建议。');
 add('R-MONITOR-006',10,true,'基准监测规则', [{field:'order.id',actual:orderId,operator:'=',threshold:orderId,ref:orderId}], '继续监测库存、采购和交期。');
 const sorted=rules.filter(x=>x.hit).sort((a,b)=>b.priority-a.priority),winner=sorted[0];
 const pegsByMaterial=new Map();for(const p of peg){const key=p.material_id;const prev=pegsByMaterial.get(key)||{material_id:key,gross_qty:0,planned_supply_qty:0,stock_allocated_qty:0,need_dates:new Set(),demand_nodes:new Set()};prev.gross_qty+=Number(p.gross_qty||0);prev.planned_supply_qty+=Number(p.planned_supply_qty||0);prev.stock_allocated_qty+=Number(p.stock_allocated_qty||0);prev.need_dates.add(p.need_date);if(p.demand_node_id)prev.demand_nodes.add(p.demand_node_id);pegsByMaterial.set(key,prev);}
 const materialEvidence=[...pegsByMaterial.values()].map(x=>({material_id:x.material_id,gross_qty:round(x.gross_qty),planned_supply_qty:round(x.planned_supply_qty),stock_allocated_qty:round(x.stock_allocated_qty),need_dates:[...x.need_dates].sort(),demand_node_ids:[...x.demand_nodes].sort()})).sort((a,b)=>b.planned_supply_qty-a.planned_supply_qty||a.material_id.localeCompare(b.material_id)).slice(0,5);
 return {order_id:orderId,scenario_id:state.scenarioId,revision:state.revision,engine:result.engine,primary_rule:winner.id,primary_action:winner.action,matched_rules:sorted.map(x=>x.id),rules,order:{id:orderId,due:order.due,qty:order.qty,product:order.product},workorder:work?{id:work.work_order_id,status:work.status,forecast_finish_date:work.forecast_finish_date,forecast_delay_days:delay,forecast_basis:work.forecast_basis}:null,mapping:mapping?{id:mapping.mapping_id,status:mapping.status,observed_value:mapping.observed_value,expected_value:mapping.expected_value,failure_code:mapping.failure_code}:null,exception_counts:Object.fromEntries([...new Set(exceptions.map(x=>x.exception_type))].sort().map(t=>[t,exceptions.filter(x=>x.exception_type===t).length])),material_evidence:materialEvidence,purchase_evidence:purchases.slice(0,8).map(x=>({pr_id:x.pr_id,material_id:x.material_id,supplier_id:x.supplier_id,planned_qty:x.planned_qty,need_date:x.need_date,release_date:x.release_date,status:x.status,shared:x.order_id==='MULTI_ORDER'})),counts:{pegging:peg.length,exceptions:exceptions.length,purchases:purchases.length},limitations:['订单关联共享采购/异常是按物料关联，不能当作该订单独占数量','预计完成日期可能仅为场景延期偏移，不代表真实产能排程','所有单据与供应商数据均为浏览器模拟，不代表真实企业记录']};
}
root.DecisionEvidence={build};if(typeof module!=='undefined'&&module.exports)module.exports={build};
})(typeof window!=='undefined'?window:globalThis);
