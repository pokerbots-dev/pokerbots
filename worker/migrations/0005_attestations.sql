CREATE TABLE attestations (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL,
  ip TEXT,
  country TEXT,
  region TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX attestations_user ON attestations(user_id, version);
INSERT INTO attestations (user_id, version, created_at) SELECT id, 1, attested_at FROM users WHERE attested_at IS NOT NULL;
