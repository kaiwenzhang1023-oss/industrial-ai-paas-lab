-- RC3.5 compensation review state additions. Isolated PG16 test only.
ALTER TABLE version_b_rc2.proposals DROP CONSTRAINT IF EXISTS proposals_status_check;
ALTER TABLE version_b_rc2.proposals ADD CONSTRAINT proposals_status_check CHECK (
 status IN ('DRAFT','CANCELLED','SUBMITTED','APPROVED','REJECTED',
 'COMPENSATION_REQUESTED','COMPENSATION_CLOSED','COMPENSATION_REJECTED'));
