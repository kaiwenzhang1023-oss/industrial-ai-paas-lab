/* RC3 isolated planning evidence; deterministic browser-only, no ERP actions. */
(function(root){'use strict';
const r=x=>Math.round((x+Number.EPSILON)*1000)/1000;
function evidence(master,state,result){
 const allocations=[],sources=[],lineage=[];
 const asOf=master.scenarios[state.scenarioId].as_of||master.metadata.as_of;
 const buckets=result.modules.buckets.filter(b=>b.gross_qty>0);
 const byMaterial={};for(const b of buckets)(byMaterial[b.material_id]??=[]).push(b);
 for(const [material,rows] of Object.entries(byMaterial)){
  rows.sort((a,b)=>a.date.localeCompare(b.date));
  const physical=[{supply_id:`SIM-OPENING:${material}:${asOf}`,material_id:material,available_date:asOf,supply_type:'OPENING_STOCK',supply_qty:Number(state.stocks[material]||0),source_system:'SIMULATED_WMS',source_document_id:`STOCK-${material}-${asOf}`,confirmed:true}];
  const undated=Number(state.receipts[material]||0);if(undated)physical.push({supply_id:`SIM-LEGACY-RECEIPT:${material}:${asOf}`,material_id:material,available_date:asOf,supply_type:'ASSUMED_RECEIPT',supply_qty:undated,source_system:'SIMULATED_WMS',source_document_id:`LEGACY-${material}`,confirmed:false});
  for(const [i,x] of (state.receiptSchedules[material]||[]).entries())physical.push({supply_id:`SIM-RECEIPT:${material}:${i}:${x.date}`,material_id:material,available_date:x.date,supply_type:'SCHEDULED_RECEIPT',supply_qty:Number(x.qty),source_system:'SIMULATED_SRM',source_document_id:String(x.source||`RECEIPT-${material}-${i}`),confirmed:false});
  const seen=new Set();for(const x of physical){if(seen.has(x.supply_id))throw Error('Duplicate supply ID');seen.add(x.supply_id);if(!Number.isFinite(x.supply_qty)||x.supply_qty<0)throw Error('Invalid supply quantity');x.allocated_qty=0;x.remaining_qty=x.supply_qty;}
  const proposals=[];
  for(const b of rows){
   const pegs=result.modules.pegging.filter(p=>p.material_id===material&&p.need_date===b.date);
   const left=pegs.map(p=>({p,remaining:p.gross_qty}));
   const eligible=physical.filter(x=>x.available_date<=b.date).sort((a,b)=>a.available_date.localeCompare(b.available_date)||a.supply_id.localeCompare(b.supply_id));
   const allocate=(s,proposal)=>{for(const d of left){const q=r(Math.min(s.remaining_qty,d.remaining));if(q<=0)continue;allocations.push({allocation_id:`SIM-ALLOC-${allocations.length+1}`,supply_id:s.supply_id,supply_type:s.supply_type,root_order_id:d.p.order_id,order_line_id:d.p.order_line_id,material_id:material,need_date:b.date,allocated_qty:q,bom_version:d.p.bom_version,pegging_id:d.p.pegging_id,demand_node_id:d.p.demand_node_id,allocation_status:proposal?'PROPOSED_NOT_RECEIVED':'SIMULATED_AVAILABLE'});s.remaining_qty=r(s.remaining_qty-q);s.allocated_qty=r(s.allocated_qty+q);d.remaining=r(d.remaining-q);}};
   for(const x of eligible)allocate(x,false);
   const proposal={supply_id:`SIM-PLAN:${material}:${b.date}`,material_id:material,available_date:b.date,supply_type:'PLANNED_NOT_RECEIVED',supply_qty:b.planned_qty,allocated_qty:0,remaining_qty:b.planned_qty,source_system:'SIMULATED_MRP',source_document_id:`PLAN-${material}-${b.date}`,confirmed:false};
   allocate(proposal,true);proposals.push(proposal);
   if(left.some(x=>x.remaining>0.001))throw Error('Unmatched demand '+material+' '+b.date);
   for(const p of pegs)lineage.push({pegging_id:p.pegging_id,root_order_id:p.order_id,order_line_id:p.order_line_id,material_id:p.material_id,need_date:p.need_date,upstream_reference:p.source,bom_version:p.bom_version,gross_qty:p.gross_qty,demand_node_id:p.demand_node_id,parent_demand_node_id:p.parent_demand_node_id,bom_path:p.bom_path,lineage_granularity:'DETERMINISTIC_BOM_DEMAND_NODE'});
  }
  sources.push(...physical,...proposals);
 }
 for(const s of sources){const used=r(allocations.filter(a=>a.supply_id===s.supply_id).reduce((v,a)=>v+a.allocated_qty,0));if(Math.abs(used-s.allocated_qty)>0.001||used>s.supply_qty+0.001||Math.abs(r(s.supply_qty-s.allocated_qty-s.remaining_qty))>0.001)throw Error('Supply conservation '+s.supply_id);}
 for(const p of result.modules.pegging){const used=r(allocations.filter(a=>a.pegging_id===p.pegging_id).reduce((v,a)=>v+a.allocated_qty,0));if(Math.abs(used-p.gross_qty)>0.001)throw Error('Demand conservation '+p.pegging_id);}
 return {allocations,sources,lineage,limitations:['Physical-like source document IDs are synthetic; no ERP/WMS/SRM connection','Opening stock is a simulated snapshot, not a physical stock-lot ledger','Planned supply is explicitly PROPOSED_NOT_RECEIVED, not inventory or a firm purchase commitment']};
}
function compare(master,state,engine,change){const base=engine.compute(master,state),candidate=JSON.parse(JSON.stringify(state));if(!change||!['receipt','stock','due'].includes(change.kind))throw Error('Unsupported what-if');const q=Number(change.qty);if(change.kind==='stock'){if(!master.items.some(i=>i.id===change.id)||!Number.isFinite(q)||q<0||q>1e8)throw Error('Invalid stock change');candidate.stocks[change.id]=q;}
 if(change.kind==='receipt'){if(!master.items.some(i=>i.id===change.id)||!Number.isFinite(q)||q<0||q>1e8||!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(change.date)||Number.isNaN(Date.parse(change.date+'T00:00:00Z')))throw Error('Invalid receipt change');candidate.receiptSchedules[change.id]=[...(candidate.receiptSchedules[change.id]||[]),{date:change.date,qty:q,source:'WHAT_IF_HYPOTHESIS'}];}
 if(change.kind==='due'){const o=candidate.orders.find(x=>x.id===change.id);if(!o||!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(change.date)||Number.isNaN(Date.parse(change.date+'T00:00:00Z')))throw Error('Invalid due date');o.due=change.date;}
 const alternative=engine.compute(master,candidate);const keys=['shortage_qty','purchase_requests','purchase_amount','review'];const delta=Object.fromEntries(keys.map(k=>[k,r(alternative.metrics[k]-base.metrics[k])]));return {change,baseline:base.metrics,candidate:alternative.metrics,delta,baseRevision:state.revision,engine:base.engine,isolated:true,assumptions:['Hypothetical input only; no real supply commitment','Recomputed using same deterministic MRP engine','No capacity/actual completion prediction']};}
root.DecisionLab={evidence,compare};if(typeof module!=='undefined'&&module.exports)module.exports={evidence,compare};
})(typeof window!=='undefined'?window:globalThis);
