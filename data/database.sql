CREATE TABLE IF NOT EXISTS env_list (
	session_id VARCHAR,
	additional_kargs VARCHAR,
	host VARCHAR,
	profile VARCHAR,
	PRIMARY KEY (session_id)
);

CREATE TABLE IF NOT EXISTS results (
  created_at VARCHAR,
	testcase VARCHAR,
	is_success VARCHAR,
	is_passed VARCHAR,
	is_abort VARCHAR,
	is_skipped VARCHAR,
	note VARCHAR,
	runtime VARCHAR,
	log TEXT,
	annotations TEXT,
	belong_to_session VARCHAR,
	FOREIGN KEY(belong_to_session) REFERENCES env_list (session_id)
);

CREATE TABLE IF NOT EXISTS artifacts (
	file_name VARCHAR,
	artifacts TEXT,
	belong_to_session VARCHAR,
	FOREIGN KEY(belong_to_session) REFERENCES env_list (session_id)
);