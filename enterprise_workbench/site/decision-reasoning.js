/* RC5 deterministic decision derivation log. Never invent underlying transaction records. */
(function(root){'use strict';
const round=n=>Math.round((Number(n)+Number.EPSILON)*1000)/1000;
const value=v=>v===undefined||v===null?'未提供':String(v);
const entry=(name,source,formula,intermediate,policy,hit,impact,reason,limits,checks)=>({name,steps:[['输入来源',source],['计算公式',formula],['中间结果',intermediate],['阈值依据',policy],['规则命中',hit],['订单影响',impact],['决策理由',reason],['数据局限性',limits]],checks});
function build(master,state,result,evidence){
 const entries=[],asOf=master.scenarios[state.scenarioId].as_of||master.metadata.as_of;
 const bySupplier=new Map(master.suppliers.map(s=>[s.id,s]));
 const relevant=evidence.rules.filter(r=>r.hit);
 for(const r of relevant){
  if(r.id==='R-SUPPLIER-003'){
   for(const p of evidence.purchase_evidence){const s=bySupplier.get(p.supplier_id);if(!s||!(Number(s.onTimeRate)<.9))continue;
    const records=s.simulated_delivery_history?.records||[];
    const total=records.length, timely=records.filter(x=>x.on_time).length, late=total-timely;
    const pct=round((total?timely/total:Number(s.onTimeRate))*100),gap=round(pct-90),valid=Number.isFinite(pct)&&gap<0;
    const avg=late?round(records.reduce((sum,x)=>sum+Number(x.delay_days||0),0)/late):0;
    const matchesSource=total>0&&round(timely/total)===round(Number(s.onTimeRate));
    entries.push({rule_id:r.id,reference:p.pr_id,...entry('供应商准交风险',`供应商 ${s.id}：${total} 条场景生成的模拟交付记录；关联采购 ${p.pr_id} / ${p.material_id}。`,`仿真准交率 = 仿真准时交付笔数 ÷ 仿真应交付笔数 × 100%；${timely} ÷ ${total} × 100% = ${pct}%。`,`模拟准时 ${timely} 笔、模拟延期 ${late} 笔；延期样本平均 ${avg} 天；低于 90% 参考线 ${round(90-pct)} 个百分点。`,'90% 为场景预设的复核参考线，不是行业强制标准。',`${pct}% < 90% = ${valid}。`,`订单 ${evidence.order_id} 通过 ${p.material_id} 与采购建议 ${p.pr_id} 关联供应商 ${s.id}；计划建议量 ${p.planned_qty}，需求日 ${p.need_date}；共享采购并非订单独占。`,'核对本次交期承诺、备选供应与库存缓冲；模拟历史指标不代表本订单必然延期。','全部交付样本为可复算的模拟生成记录，不是真实供应商交付历史；样本量和分布由仿真设定，不能推断真实违约概率。',[{name:'样本准交率与主数据一致',pass:matchesSource},{name:'阈值比较',pass:valid}])});
   }continue;
  }
  if(r.id==='R-RELEASE-002'){
   for(const c of r.checks){const p=evidence.purchase_evidence.find(x=>x.pr_id===c.ref);if(!p)continue;const item=master.items.find(x=>x.id===p.material_id);const lead=item?.leadDays;const derived=Number.isFinite(Number(lead))?new Date(Date.parse(p.need_date+'T00:00:00Z')-Number(lead)*86400000).toISOString().slice(0,10):null;
    entries.push({rule_id:r.id,reference:p.pr_id,...entry('采购释放逾期',`purchase[${p.pr_id}]：需求日 ${p.need_date}，释放日 ${p.release_date}；items[${p.material_id}].leadDays=${value(lead)}；场景 as_of=${asOf}`,`释放日=需求日−提前期（按自然日）；逾期条件：释放日 < 场景基准日。`,`根据需求日与提前期推算 ${value(derived)}；引擎记录 ${p.release_date}；基准日 ${asOf}。`,'基准日取场景 as_of；自然日提前期为模拟假设，不含工作日、节假日或供应商确认。',`${p.release_date} < ${asOf} = ${p.release_date<asOf}。`,`订单 ${evidence.order_id} 关联 PR ${p.pr_id}，建议量 ${p.planned_qty}；逾期是计划释放时点落后，不代表采购已经执行或实际逾期。`,'人工确认是否补发采购、调整交期或使用替代库存。','缺少真实采购下单时间、交货承诺、供应商日历。',[{name:'释放日与提前期一致',pass:derived===p.release_date},{name:'逾期比较',pass:p.release_date<asOf}])});
   }continue;
  }
  if(r.id==='R-MAP-001'){
   const m=evidence.mapping;entries.push({rule_id:r.id,reference:m?.id||'MISSING',...entry('映射阻断',`mapping[${value(m?.id)}]：状态=${value(m?.status)}；观测值=${value(m?.observed_value)}；期望值=${value(m?.expected_value)}；失败码=${value(m?.failure_code)}`,'规则：mapping.status === BLOCKED_REVIEW；若观测值和期望值存在则额外检查是否相等。',`状态比较：${value(m?.status)} === BLOCKED_REVIEW；版本比较：${value(m?.observed_value)} 与 ${value(m?.expected_value)}。`,'映射校验未通过时不应继续模拟下游采购/生产执行，属于案例安全门禁。',`BLOCKED_REVIEW=${m?.status==='BLOCKED_REVIEW'}。`,`订单 ${evidence.order_id} 关联映射 ${value(m?.id)}，下游模拟流程应被阻断。`,'核对 BOM 发布版本、映射字段与校验结果，重新计算后再复核。','仅为模拟映射状态；未连接 ERP/MES/SRM 的真实版本主数据。',[{name:'阻断状态一致',pass:m?.status==='BLOCKED_REVIEW'}])});continue;
  }
  if(r.id==='R-DELAY-004'){
   const w=evidence.workorder,d=Number(w?.forecast_delay_days||0);
   entries.push({rule_id:r.id,reference:w?.id||'MISSING',...entry('模拟延期',`workorder[${value(w?.id)}].forecast_delay_days=${d}；订单交期=${evidence.order.due}；模拟预计日期=${value(w?.forecast_finish_date)}。`,'延期命中条件：forecast_delay_days > 0；预计日期的生成依据以 forecast_basis 为准。',`模拟延期偏移 ${d} 天；预计日期 ${value(w?.forecast_finish_date)}；依据 ${value(w?.forecast_basis)}。`,'本案例将正的模拟延期偏移视为风险；不是基于有限产能排程得到的真实延期。',`${d} > 0 = ${d>0}。`,`订单 ${evidence.order_id} 可能存在模拟交期风险，但不能据此对外承诺完成日期。`,'核实物料到货、产能和实际工单进度后再决定交期调整。','缺少真实产能、班次、设备负荷与现场工单事件。',[{name:'正延期判断',pass:d>0}])});continue;
  }
  if(r.id==='R-PR-005'){
   const ps=evidence.purchase_evidence;entries.push({rule_id:r.id,reference:ps.map(x=>x.pr_id).join(', '),...entry('采购建议存在',`result.modules.purchase 关联订单 ${evidence.order_id}：${ps.map(x=>x.pr_id).join('、')}；展示前 ${ps.length} 条。`,'规则命中条件：关联采购建议条数 > 0；单笔采购建议由 MRP 按日期分桶、可用库存、MOQ/批量约束生成。',`关联条数=${evidence.counts.purchases}；前 5 种物料 Pegging 汇总：${evidence.material_evidence.map(x=>`${x.material_id}(毛需求${x.gross_qty}−分配库存${x.stock_allocated_qty}=计划供应分摊${x.planned_supply_qty})`).join('；')}。`,'关联数量大于 0 是规则触发条件，不是采购金额或库存风险阈值。',`${evidence.counts.purchases} > 0 = ${evidence.counts.purchases>0}。`,'共享 PR 仅按物料关联，不能将其全部数量计入该订单；订单级 Pegging 可核对分摊。','查看缺口与采购释放日，人工确认是否采购；计划供应不等于实际到货。','展示物料仅为前 5 种；共享物料、MOQ 和批量可能造成采购量与订单分摊不同。',[{name:'关联采购数量',pass:evidence.counts.purchases>0},...evidence.material_evidence.map(x=>({name:`${x.material_id} Pegging 分摊守恒`,pass:Math.abs(round(x.gross_qty-x.stock_allocated_qty-x.planned_supply_qty))<.001}))])});continue;
  }
  if(r.id==='R-MONITOR-006')entries.push({rule_id:r.id,reference:evidence.order_id,...entry('基准监测',`订单 ${evidence.order_id}，当前修订 ${evidence.revision}。`,'兜底规则恒为 true；只有更高优先级规则未命中时才作为主要建议。',`已命中更高优先级规则数=${relevant.filter(x=>x.id!=='R-MONITOR-006').length}。`,'兜底规则优先级为 10，低于其他风险规则。','true；作为同时命中规则不代表没有风险。','用于解释为何保留持续监测建议。','按最高优先级命中规则执行人工复核，不应将兜底规则覆盖高风险。','兜底规则不提供风险消除证明。',[{name:'兜底规则恒命中',pass:true}])});
 }
 const failed=entries.flatMap(e=>e.checks.filter(c=>!c.pass).map(c=>({rule_id:e.rule_id,reference:e.reference,check:c.name})));
 return {schema_version:'RC5_DECISION_REASONING_V1',order_id:evidence.order_id,scenario_id:state.scenarioId,revision:state.revision,engine:result.engine,primary_rule:evidence.primary_rule,entries,validation:{status:failed.length?'FAIL':'PASS',checked:entries.reduce((a,e)=>a+e.checks.length,0),failed},provenance:'STRUCTURED_DETERMINISTIC_NO_LLM'};
}
root.DecisionReasoning={build};if(typeof module!=='undefined'&&module.exports)module.exports={build};
})(typeof window!=='undefined'?window:globalThis);
