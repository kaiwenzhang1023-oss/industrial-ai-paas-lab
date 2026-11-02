"""Immutable B01 mapping profile; no runtime-supplied rule execution."""
from types import MappingProxyType
B01_MAPPING_ID = 'B01-MRP-BUY-SRM-PR'
B01_VERSION = '1.0.0'
# Rule declarations intentionally immutable, including nested arguments.
RULES = (
    MappingProxyType({'op':'DIRECT','source':'source_run_id','target':'source_run_id'}),
    MappingProxyType({'op':'DIRECT','source':'source_result_hash','target':'source_result_hash'}),
    MappingProxyType({'op':'RENAME','source':'source_plan_id','target':'source_plan_id'}),
    MappingProxyType({'op':'RENAME','source':'material_id','target':'material_id'}),
    MappingProxyType({'op':'TYPE_CAST','source':'quantity','target':'quantity','type':'decimal'}),
    MappingProxyType({'op':'DIRECT','source':'uom','target':'uom'}),
    MappingProxyType({'op':'DATE_FORMAT','source':'need_date','target':'need_date'}),
    MappingProxyType({'op':'DATE_FORMAT','source':'release_date','target':'release_date'}),
    MappingProxyType({'op':'DIRECT','source':'bom_version','target':'bom_version'}),
    MappingProxyType({'op':'DIRECT','source':'pr_id','target':'pr_id'}),
)
PUBLISHED = MappingProxyType({B01_VERSION: RULES})
TARGET_FIELDS = frozenset({'pr_id','source_run_id','source_result_hash','source_plan_id','material_id','quantity','uom','need_date','release_date','bom_version'})
