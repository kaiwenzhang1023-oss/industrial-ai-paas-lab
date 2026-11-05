"""Existing backend scenario aliases; no fake price/margin/physical delay facts."""
SCENARIOS={
 'G01':{'backend':'B','title':'关键物料供应风险','claim':'计划补货需求；非已确认停工','entry':'MRP 计划','expected':'NET_REPLENISHMENT_NOT_SHORTAGE'},
 'G02':{'backend':'C','title':'客户交期调整','claim':'观察需求时间变化；非已确认供应商延期','entry':'MRP 计划','expected':'DUE_DATE_CHANGED'},
 'G03':{'backend':'D','title':'BOM 用量异常','claim':'人工复核异常用量；不自动批准执行','entry':'MRP 计划','expected':'HUMAN_REVIEW_REQUIRED'},
}
def scenario(key):
    if key not in SCENARIOS:raise ValueError('UNKNOWN_SCENARIO')
    return dict(SCENARIOS[key])
