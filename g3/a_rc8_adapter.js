/* Frozen Version A RC8 native engine adapter. This file must not modify engine.js.
   Receive RC2 canonical snapshot JSON from stdin; emit A daily-bucket lines. */
'use strict';
const fs=require('fs');
const path=require('path');
const engine=require(path.resolve(__dirname,'../enterprise_workbench/site/engine.js'));
function adapt(snapshot){
 if(!snapshot||!Array.isArray(snapshot.orders)||!snapshot.items||!Array.isArray(snapshot.bom))throw Error('INVALID_CANONICAL_SNAPSHOT');
 const items=Object.entries(snapshot.items).map(([id,m])=>({
   id,type:m.kind,leadDays:m.lead_days||0,on_hand:Number(m.on_hand||0),
   reserved:Number(m.reserved||0),blocked:Number(m.blocked||0),safety:Number(m.safety||0),
   moq:Number(m.moq||0),lot:Number(m.lot||1),
   receipts:(m.receipts||[]).map(([date,qty])=>({date,qty:Number(qty)}))
 }));
 const orders=snapshot.orders.map(o=>({id:o.order_id,product:o.product,qty:Number(o.qty),due:o.due,priority:Number(o.priority||0)}));
 const bom=snapshot.bom.map(([parent,child,qty])=>({parent,child,qty:Number(qty)}));
 const roots=new Set(orders.map(o=>o.product));
 const rootLeads=new Set(orders.map(o=>Number(snapshot.items[o.product]?.lead_days)));
 if(rootLeads.size!==1||roots.size!==1)throw Error('ROOT_POLICY_NOT_COMPARABLE');
 // Version A's public deterministic planBuckets uses root lead as explicit contract.
 return engine.planBuckets(orders,items,bom,snapshot.as_of,[...rootLeads][0]);
}
let data=''; process.stdin.setEncoding('utf8');
process.stdin.on('data',chunk=>{data+=chunk;if(data.length>1048576){process.stderr.write('SNAPSHOT_TOO_LARGE\n');process.exit(2)}});
process.stdin.on('end',()=>{try{const snapshot=JSON.parse(data);process.stdout.write(JSON.stringify({engine:'VERSION_A_RC8_NATIVE_JS_PLAN_BUCKETS',lines:adapt(snapshot)}))}
 catch(err){process.stderr.write('A_ADAPTER_ERROR:'+String(err.message).replace(/[^A-Z0-9_ ]/ig,'').slice(0,80)+'\n');process.exitCode=2}});
module.exports={adapt};
