ALTER TABLE stripes ADD COLUMN channel_r_gamma REAL DEFAULT 2.8;
ALTER TABLE stripes ADD COLUMN channel_g_gamma REAL DEFAULT 2.8;
ALTER TABLE stripes ADD COLUMN channel_b_gamma REAL DEFAULT 2.8;

REPLACE INTO meta (`option`, `value`) VALUES (`db_version`, `2`);