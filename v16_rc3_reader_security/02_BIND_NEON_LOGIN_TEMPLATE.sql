-- FIRST create a NEW LOGIN role through Neon dev branch Roles UI; store its password ONLY in local environment.
-- Replace __DEV_LOGIN_ROLE__ with the exact role name; use a plain PostgreSQL identifier.
-- Never run until you have confirmed the selected Neon branch is dev-v1-6-backend-pg18.
-- This GRANT is a separate step; do not give the reader role to neondb_owner or postgres.
BEGIN;
GRANT portfolio_v16_reader TO __DEV_LOGIN_ROLE__;
COMMIT;
