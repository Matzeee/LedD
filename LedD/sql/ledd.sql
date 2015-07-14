CREATE TABLE `stripes` (
	`id`	INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
	`name`	TEXT,
	`rgb`	INTEGER,
	`controller_id`	INTEGER,
	`channel_r`	INTEGER,
	`channel_g`	INTEGER,
	`channel_b`	INTEGER
);
CREATE TABLE "meta" (
	`option`	TEXT,
	`value`	TEXT
);
INSERT INTO `meta` VALUES ('db_version','1');
CREATE TABLE "controller" (
	`id`	INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
	`address`	TEXT,
	`i2c_device`	TEXT,
	`channels`	INTEGER,
	`pwm_freq`	INTEGER
);
COMMIT;
