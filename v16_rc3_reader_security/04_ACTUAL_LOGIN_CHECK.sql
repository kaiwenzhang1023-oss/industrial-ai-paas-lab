-- Run ONLY using the new reader LOGIN credentials (not the owner SQL Editor session).
SELECT current_user, session_user, current_database(),
 has_table_privilege(current_user,'mes_v13.work_orders','SELECT') AS mes_read,
 has_table_privilege(current_user,'mapping_v14.public_versions','SELECT') AS mapping_view_read,
 has_table_privilege(current_user,'mapping_v14.mapping_versions','SELECT') AS mapping_base_read,
 has_table_privilege(current_user,'mes_v13.work_orders','INSERT') AS mes_write;
-- Negative permission tests are done by checking has_*_privilege, not executing destructive DML.
