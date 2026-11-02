-- READ ONLY: validate template role permissions; execute in DEV branch only.
SELECT r.rolname,r.rolcanlogin,
 has_schema_privilege(r.rolname,'mes_v13','USAGE') mes_usage,
 has_schema_privilege(r.rolname,'srm_v14','USAGE') srm_usage,
 has_schema_privilege(r.rolname,'mapping_v14','USAGE') mapping_usage,
 has_table_privilege(r.rolname,'mes_v13.work_orders','SELECT') mes_read,
 has_table_privilege(r.rolname,'srm_v14.purchase_requisitions','SELECT') srm_pr_read,
 has_table_privilege(r.rolname,'srm_v14.supply_exceptions','SELECT') srm_ex_read,
 has_table_privilege(r.rolname,'mapping_v14.public_versions','SELECT') mapping_versions_read,
 has_table_privilege(r.rolname,'mapping_v14.public_executions','SELECT') mapping_executions_read,
 has_table_privilege(r.rolname,'mapping_v14.mapping_versions','SELECT') mapping_base_read,
 has_table_privilege(r.rolname,'mes_v13.work_orders','INSERT') mes_insert,
 has_table_privilege(r.rolname,'srm_v14.purchase_requisitions','UPDATE') srm_update,
 has_schema_privilege(r.rolname,'mes_v13','CREATE') mes_create
FROM pg_roles r WHERE r.rolname='portfolio_v16_reader';
-- After creating the login and binding it, run the above SELECT with rolname = your login role as well.
