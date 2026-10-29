ALTER TABLE games ADD COLUMN finished_at TEXT;
CREATE INDEX games_finished ON games(finished_at);
