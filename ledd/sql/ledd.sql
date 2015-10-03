CREATE TABLE `stripes` (
	`id`	INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
	`name`	TEXT,
	`rgb`	INTEGER,
	`controller_id`	INTEGER,
	`channel_r`	INTEGER,
	`channel_g`	INTEGER,
	`channel_b`	INTEGER,
	`channel_r_gamma` REAL DEFAULT 2.8,
	`channel_g_gamma` REAL DEFAULT 2.8,
	`channel_b_gamma` REAL DEFAULT 2.8
);
CREATE TABLE "meta" (
	`option` TEXT,
	`value` TEXT
);
INSERT INTO `meta` VALUES ('db_version','2');
CREATE TABLE "controller" (
	`id`	INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
	`address`	TEXT,
	`i2c_device`	INTEGER,
	`channels`	INTEGER,
	`pwm_freq`	INTEGER
);