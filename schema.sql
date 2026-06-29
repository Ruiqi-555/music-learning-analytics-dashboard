PRAGMA foreign_keys = ON;

-- Core user tables
CREATE TABLE IF NOT EXISTS users (
  user_id            INTEGER PRIMARY KEY,
  email              TEXT,
  phone              TEXT,
  nickname           TEXT,
  gender             TEXT,
  birth_year         INTEGER,
  region             TEXT,
  register_source    TEXT,
  register_time      TEXT NOT NULL,
  invited_by_user_id INTEGER,
  status             TEXT DEFAULT 'active',
  created_at         TEXT,
  updated_at         TEXT
);

CREATE TABLE IF NOT EXISTS user_preferences (
  user_id        INTEGER PRIMARY KEY,
  fav_genres     TEXT,
  fav_scenes     TEXT,
  dislike_genres TEXT,
  extra_info     TEXT,
  created_at     TEXT,
  updated_at     TEXT,
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Logs
CREATE TABLE IF NOT EXISTS listening_logs (
  log_id        INTEGER PRIMARY KEY,
  user_id       INTEGER NOT NULL,
  play_time     TEXT NOT NULL,
  duration_sec  INTEGER,
  track_id      INTEGER,
  genre         TEXT,
  is_skipped    INTEGER,
  device_type   TEXT,
  from_recommend INTEGER,
  created_at    TEXT,
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS feedbacks (
  feedback_id   INTEGER PRIMARY KEY,
  user_id       INTEGER NOT NULL,
  feedback_time TEXT NOT NULL,
  rating        INTEGER,
  channel       TEXT,
  feedback_type TEXT,
  comment_text  TEXT,
  created_at    TEXT,
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Analysis Results
CREATE TABLE IF NOT EXISTS user_profiles (
  user_id             INTEGER PRIMARY KEY,
  mbti_guess          TEXT,
  main_interest       TEXT,
  active_time_pattern TEXT,
  spending_level      TEXT,
  churn_risk_level    TEXT,
  keywords_summary    TEXT,
  last_profile_update TEXT,
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS user_segments (
  segment_id   INTEGER PRIMARY KEY,
  segment_name TEXT,
  description  TEXT
);

CREATE TABLE IF NOT EXISTS user_segment_membership (
  user_id     INTEGER NOT NULL,
  segment_id  INTEGER NOT NULL,
  assigned_by TEXT,
  assigned_at TEXT,
  PRIMARY KEY (user_id, segment_id),
  FOREIGN KEY (user_id) REFERENCES users(user_id),
  FOREIGN KEY (segment_id) REFERENCES user_segments(segment_id)
);

CREATE TABLE IF NOT EXISTS feedback_topics (
  feedback_id   INTEGER NOT NULL,
  topic_label   TEXT NOT NULL,
  sentiment_score REAL,
  keywords        TEXT,
  FOREIGN KEY (feedback_id) REFERENCES feedbacks(feedback_id)
);

-- Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_reg_time ON users(register_time);
CREATE INDEX IF NOT EXISTS idx_logs_user_time ON listening_logs(user_id, play_time);
CREATE INDEX IF NOT EXISTS idx_logs_play_time ON listening_logs(play_time);
CREATE INDEX IF NOT EXISTS idx_feedbacks_user ON feedbacks(user_id);
