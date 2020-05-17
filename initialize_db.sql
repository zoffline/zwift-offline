CREATE TABLE version ( version INTEGER );

INSERT INTO version VALUES (2);

/* column names must match protobuf field names */

CREATE TABLE activity (
	id TEXT PRIMARY KEY, /* uint64 */
	player_id TEXT, /* uint64 */
	f3 INTEGER,
	name TEXT,
	f5 INTEGER,
	f6 INTEGER,
	start_date TEXT,
	end_date TEXT,
	distance REAL,
	avg_heart_rate REAL,
	max_heart_rate REAL,
	avg_watts REAL,
	max_watts REAL,
	avg_cadence REAL,
	max_cadence REAL,
	avg_speed REAL,
	max_speed REAL,
	calories REAL,
	total_elevation REAL,
	strava_upload_id TEXT, /* uint64 */
	strava_activity_id TEXT, /* uint64 */
	f23 INTEGER,
	fit BLOB,
	fit_filename TEXT,
	f29 INTEGER,
	date TEXT
);

CREATE TABLE goal (
	id TEXT PRIMARY KEY, /* uint64 */
	player_id TEXT, /* uint64 */
	f3 INTEGER,
	name TEXT,
	type INTEGER,
	periodicity INTEGER,
	target_distance REAL,
	target_duration REAL,
	actual_distance REAL,
	actual_duration REAL,
	created_on TEXT, /* uint64 */
	period_end_date TEXT, /* uint64 */
	f13 TEXT /* uint64 */
);

CREATE TABLE segment_result (
	id TEXT PRIMARY KEY, /* uint64 */
	player_id TEXT, /* uint64 */
	f3 INTEGER,
	f4 INTEGER,
	segment_id TEXT, /* uint64 */
	event_subgroup_id TEXT, /* uint64 */
	first_name TEXT,
	last_name TEXT,
	world_time TEXT, /* uint64 */
	finish_time_str TEXT,
	elapsed_ms TEXT, /* uint64 */
	f12 NUMERIC, /* bool */
	f13 INTEGER,
	f14 INTEGER,
	f15 INTEGER,
	f16 NUMERIC, /* bool */
	f17 TEXT,
	f18 TEXT, /* uint64 */
	f19 INTEGER,
	f20 INTEGER
);
