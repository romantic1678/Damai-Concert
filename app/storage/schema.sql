-- Damai Ticket Assistant schema v1 base + v2 columns in CREATE for new DBs
-- Incremental upgrades for existing DBs are applied in database.migrate() v2.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS concert_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  city TEXT,
  official_url TEXT,
  open_sale_at TEXT,
  monitor_enabled INTEGER NOT NULL DEFAULT 0 CHECK (monitor_enabled IN (0, 1)),
  note TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  artist_name TEXT,
  show_date TEXT,
  session_name TEXT,
  target_price REAL,
  target_tier TEXT,
  ticket_quantity INTEGER,
  status TEXT NOT NULL DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_concert_tasks_open_sale_at
  ON concert_tasks(open_sale_at);
CREATE INDEX IF NOT EXISTS idx_concert_tasks_monitor
  ON concert_tasks(monitor_enabled);
CREATE INDEX IF NOT EXISTS idx_concert_tasks_status
  ON concert_tasks(status);
CREATE INDEX IF NOT EXISTS idx_concert_tasks_artist
  ON concert_tasks(artist_name);
CREATE INDEX IF NOT EXISTS idx_concert_tasks_show_date
  ON concert_tasks(show_date);

CREATE TABLE IF NOT EXISTS status_baselines (
  task_id INTEGER PRIMARY KEY,
  established_at TEXT NOT NULL,
  normalized_status TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  raw_excerpt TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (task_id) REFERENCES concert_tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sale_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  fetched_at TEXT NOT NULL,
  source_url TEXT NOT NULL,
  raw_excerpt TEXT NOT NULL,
  normalized_status TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  is_baseline INTEGER NOT NULL DEFAULT 0 CHECK (is_baseline IN (0, 1)),
  FOREIGN KEY (task_id) REFERENCES concert_tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sale_snapshots_task_time
  ON sale_snapshots(task_id, fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_sale_snapshots_hash
  ON sale_snapshots(task_id, content_hash);

CREATE TABLE IF NOT EXISTS reminder_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  scheduler_job_id TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL,
  run_at TEXT,
  interval_seconds INTEGER,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (task_id) REFERENCES concert_tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reminder_jobs_task
  ON reminder_jobs(task_id, status);

CREATE TABLE IF NOT EXISTS notification_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER,
  channel TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  success INTEGER NOT NULL CHECK (success IN (0, 1)),
  error_message TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (task_id) REFERENCES concert_tasks(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_notification_logs_created
  ON notification_logs(created_at DESC);

CREATE TABLE IF NOT EXISTS browser_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id INTEGER NOT NULL,
  official_url TEXT NOT NULL,
  launched_at TEXT NOT NULL,
  closed_at TEXT,
  takeover_state TEXT NOT NULL,
  notes TEXT,
  FOREIGN KEY (task_id) REFERENCES concert_tasks(id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS notification_dedupe (
  dedupe_key TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  task_id INTEGER,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notification_dedupe_kind
  ON notification_dedupe(kind);
