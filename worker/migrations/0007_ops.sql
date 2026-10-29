CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

ALTER TABLE users ADD COLUMN suspended_at TEXT;

-- Rebuild the ledger to allow manual adjustments with a reason.
CREATE TABLE ledger_new (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  kind TEXT NOT NULL CHECK (kind IN ('deposit', 'buyin', 'payout', 'rake', 'refund', 'withdrawal', 'adjustment')),
  amount INTEGER NOT NULL,
  ref TEXT NOT NULL,
  note TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (kind, ref)
);
INSERT INTO ledger_new (id, user_id, kind, amount, ref, created_at) SELECT id, user_id, kind, amount, ref, created_at FROM ledger;
DROP TABLE ledger;
ALTER TABLE ledger_new RENAME TO ledger;
CREATE INDEX ledger_user ON ledger(user_id);
