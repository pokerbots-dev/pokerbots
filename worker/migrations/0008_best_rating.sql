ALTER TABLE ratings ADD COLUMN best REAL;
UPDATE ratings SET best = rating;
