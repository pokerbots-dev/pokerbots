CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  github_id INTEGER NOT NULL UNIQUE,
  login TEXT NOT NULL,
  wallet TEXT,
  attested_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  expires_at INTEGER NOT NULL
);

CREATE TABLE versions (
  user_id INTEGER NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL,
  size INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, version)
);

CREATE TABLE deployments (
  user_id INTEGER NOT NULL REFERENCES users(id),
  mode TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
  version INTEGER NOT NULL,
  PRIMARY KEY (user_id, mode)
);

CREATE TABLE ratings (
  user_id INTEGER NOT NULL REFERENCES users(id),
  mode TEXT NOT NULL,
  rating REAL NOT NULL DEFAULT 1500,
  games INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, mode)
);

CREATE TABLE games (
  id TEXT PRIMARY KEY,
  mode TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('queued', 'done', 'failed')),
  seed INTEGER NOT NULL,
  hands INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX games_created ON games(created_at);

CREATE TABLE seats (
  game_id TEXT NOT NULL REFERENCES games(id),
  seat INTEGER NOT NULL,
  user_id INTEGER REFERENCES users(id),
  version INTEGER,
  house TEXT,
  place INTEGER,
  late INTEGER,
  errors INTEGER,
  PRIMARY KEY (game_id, seat)
);
CREATE INDEX seats_user ON seats(user_id, game_id);

-- Amounts are USDC micro-units (1 = $0.000001); user_id NULL is the house.
CREATE TABLE ledger (
  id INTEGER PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  kind TEXT NOT NULL CHECK (kind IN ('deposit', 'buyin', 'payout', 'rake', 'refund', 'withdrawal')),
  amount INTEGER NOT NULL,
  ref TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (kind, ref)
);
CREATE INDEX ledger_user ON ledger(user_id);

CREATE TABLE deposits (
  signature TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  amount INTEGER NOT NULL,
  last_valid INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('prepared', 'sent', 'credited', 'failed')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE withdrawals (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  amount INTEGER NOT NULL,
  address TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'sent', 'done', 'failed', 'rejected')),
  signature TEXT,
  last_valid INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX withdrawals_status ON withdrawals(status, created_at);
