-- M2-02-02: existing mock_erp.bom_versions uses inclusive effective_to.
-- Versioned Python engine uses [from,to) to avoid boundary ambiguity.
-- Migration converts old inclusive dates to exclusive dates (+1 day).
-- Requires maintenance window and data backup; test on staging first.
BEGIN;
ALTER TABLE mock_erp.bom_versions ADD COLUMN IF NOT EXISTS effective_to_exclusive date;
UPDATE mock_erp.bom_versions
SET effective_to_exclusive = CASE WHEN effective_to IS NULL THEN NULL ELSE effective_to + 1 END
WHERE effective_to_exclusive IS NULL;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'bom_exclusive_interval_check'
                 AND conrelid = 'mock_erp.bom_versions'::regclass) THEN
    ALTER TABLE mock_erp.bom_versions ADD CONSTRAINT bom_exclusive_interval_check
      CHECK (effective_to_exclusive IS NULL OR effective_to_exclusive > effective_from);
  END IF;
END $$;
-- Released intervals are checked in application validation; DB overlap
-- exclusion requires btree_gist and a deployment-specific migration.
COMMIT;
