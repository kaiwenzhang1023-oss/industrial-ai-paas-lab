#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
command -v docker >/dev/null || { echo 'BLOCKED: docker is required'; exit 2; }
docker compose up -d postgres
for i in $(seq 1 40); do
  if docker compose exec -T postgres pg_isready -U lab -d industrial_lab >/dev/null 2>&1; then break; fi
  sleep 2
done
docker compose exec -T postgres pg_isready -U lab -d industrial_lab
# Separate disposable test database; never use production.
if ! docker compose exec -T postgres psql -U lab -d postgres -Atqc "SELECT 1 FROM pg_database WHERE datname='industrial_lab_test'" | grep -qx 1; then
  docker compose exec -T postgres psql -U lab -d postgres -v ON_ERROR_STOP=1 -c 'CREATE DATABASE industrial_lab_test'
fi
for file in schema.sql 003_v03.sql 004_snapshot_fence.sql 006_m2_integration.sql 007_normalized_pegging.sql; do
  echo "Applying $file to industrial_lab_test"
  docker compose exec -T postgres psql -U lab -d industrial_lab_test -v ON_ERROR_STOP=1 < "database/$file"
done
export TEST_DATABASE_URL='postgresql://lab:local_demo_only@localhost:5432/industrial_lab_test'
cd backend
python -m pip install -e '.[test]'
python -m pytest -v -m integration | tee "$ROOT/pg16_integration.log"
python -m pytest -q | tee "$ROOT/pg16_full_regression.log"
