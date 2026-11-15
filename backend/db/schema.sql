-- SpaceScan (Scan Space · ARES VII) — Phase 0 Canonical Database Schema
-- Engine: SQLite 3 (STRICT tables, WAL mode, Append-Only measurements, FTS5, JSON1)

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

-- ============================================================================
-- DEV 1: Mission, Crew, Baselines, Measurements (Append-Only), Environment,
--        Streaks, and Ground Store-and-Forward Outbox
-- ============================================================================

CREATE TABLE IF NOT EXISTS mission (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  mission_code TEXT NOT NULL,
  mission_name TEXT NOT NULL,
  current_stage TEXT NOT NULL CHECK (current_stage IN ('LAUNCH', 'MISSION', 'RETURN')),
  launch_utc TEXT NOT NULL,
  planned_return_utc TEXT NOT NULL,
  earth_latency_min INTEGER NOT NULL DEFAULT 12 CHECK (earth_latency_min >= 0),
  quiet_hours_start_utc TEXT NOT NULL DEFAULT '22:00',
  quiet_hours_end_utc TEXT NOT NULL DEFAULT '06:00',
  updated_at_utc TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS crew_members (
  id TEXT PRIMARY KEY,                              -- e.g. 'ID-01'
  code TEXT NOT NULL UNIQUE,                        -- e.g. 'ID·01'
  full_name TEXT NOT NULL,                          -- e.g. 'Elena Vargas'
  role TEXT NOT NULL CHECK (role IN ('ASTRONAUT', 'PILOT', 'OPERATOR', 'PHYSICIAN')),
  pin_hash TEXT NOT NULL,                           -- Argon2id hash of 4-digit PIN
  age INTEGER CHECK (age IS NULL OR age > 0),
  sex TEXT CHECK (sex IS NULL OR sex IN ('F', 'M', 'X')),
  blood_type TEXT,
  height_cm REAL CHECK (height_cm IS NULL OR height_cm > 0),
  is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
  failed_attempts INTEGER NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
  locked_until_utc TEXT,
  created_at_utc TEXT NOT NULL,
  updated_at_utc TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS metric_catalog (
  metric_key TEXT PRIMARY KEY,                      -- e.g. 'optic_sheath_right_mm', 'sleep_total_min'
  display_name_en TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN (
    'VITALS', 'BIOMETRICS', 'HABITS', 'LABS', 'VISION', 'RESPIRATORY', 'ENVIRONMENT'
  )),
  unit TEXT NOT NULL,
  nominal_min REAL NOT NULL,
  nominal_max REAL NOT NULL,
  warning_min REAL,
  warning_max REAL,
  critical_min REAL,
  critical_threshold REAL,
  recommended_frequency_hours REAL NOT NULL DEFAULT 24.0 CHECK (recommended_frequency_hours > 0),
  clinical_reference TEXT NOT NULL                  -- Scientific source reference for audit/reports
) STRICT;

CREATE TABLE IF NOT EXISTS baselines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  crew_id TEXT NOT NULL REFERENCES crew_members(id),
  metric_key TEXT NOT NULL REFERENCES metric_catalog(metric_key),
  mean_val REAL NOT NULL,
  std_dev REAL NOT NULL DEFAULT 0.0 CHECK (std_dev >= 0),
  sample_count INTEGER NOT NULL DEFAULT 1 CHECK (sample_count >= 1),
  computed_at_utc TEXT NOT NULL,
  UNIQUE (crew_id, metric_key)
) STRICT;

CREATE TABLE IF NOT EXISTS measurements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  crew_id TEXT NOT NULL REFERENCES crew_members(id),
  metric_key TEXT NOT NULL REFERENCES metric_catalog(metric_key),
  mission_stage TEXT NOT NULL CHECK (mission_stage IN ('LAUNCH', 'MISSION', 'RETURN')),
  source_type TEXT NOT NULL DEFAULT 'MANUAL' CHECK (source_type IN ('MANUAL', 'AUTO')),
  recorded_at_utc TEXT NOT NULL,
  value_num REAL,
  payload_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(payload_json))
) STRICT;

CREATE INDEX IF NOT EXISTS idx_measurements_crew_metric_ts
  ON measurements (crew_id, metric_key, recorded_at_utc DESC);

CREATE INDEX IF NOT EXISTS idx_measurements_stage_ts
  ON measurements (mission_stage, recorded_at_utc DESC);

-- RNF 5: Biomedical immutability (Append-Only enforcement on measurements)
CREATE TRIGGER IF NOT EXISTS trg_measurements_no_update
BEFORE UPDATE ON measurements
BEGIN
  SELECT RAISE(ABORT, 'Measurements table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_measurements_no_delete
BEFORE DELETE ON measurements
BEGIN
  SELECT RAISE(ABORT, 'Measurements table is append-only');
END;

CREATE TABLE IF NOT EXISTS environment_readings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  co2_ppm REAL NOT NULL CHECK (co2_ppm >= 0),
  noise_dba REAL NOT NULL CHECK (noise_dba >= 0),
  temp_c REAL NOT NULL,
  humidity_pct REAL NOT NULL CHECK (humidity_pct BETWEEN 0 AND 100),
  radiation_msv REAL NOT NULL DEFAULT 0.0 CHECK (radiation_msv >= 0),
  solar_event_flag INTEGER NOT NULL DEFAULT 0 CHECK (solar_event_flag IN (0, 1)),
  recorded_at_utc TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_environment_readings_ts
  ON environment_readings (recorded_at_utc DESC);

CREATE TABLE IF NOT EXISTS streak_days (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  crew_id TEXT NOT NULL REFERENCES crew_members(id),
  streak_date_utc TEXT NOT NULL,                    -- YYYY-MM-DD in UTC
  logs_completed INTEGER NOT NULL DEFAULT 0 CHECK (logs_completed >= 0),
  habits_met INTEGER NOT NULL DEFAULT 0 CHECK (habits_met IN (0, 1)),
  daily_compliant INTEGER NOT NULL DEFAULT 0 CHECK (daily_compliant IN (0, 1)),
  updated_at_utc TEXT NOT NULL,
  UNIQUE (crew_id, streak_date_utc)
) STRICT;

CREATE TABLE IF NOT EXISTS ground_outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  packet_type TEXT NOT NULL DEFAULT 'DAILY_SUMMARY' CHECK (packet_type IN (
    'DAILY_SUMMARY', 'CLINICAL_REPORT', 'CREW_UPDATE', 'GROUND_DIRECTIVE'
  )),
  direction TEXT NOT NULL DEFAULT 'OUTBOUND' CHECK (direction IN ('OUTBOUND', 'INBOUND')),
  crew_id TEXT REFERENCES crew_members(id),
  bundle_json TEXT NOT NULL CHECK (json_valid(bundle_json)),
  created_at_utc TEXT NOT NULL,
  deliver_after_utc TEXT NOT NULL,                  -- Calculated on enqueue (e.g., +12 min latency)
  delivered_at_utc TEXT,
  status TEXT NOT NULL CHECK (status IN ('QUEUED', 'IN_TRANSIT', 'DELIVERED', 'ACKNOWLEDGED'))
) STRICT;

CREATE INDEX IF NOT EXISTS idx_ground_outbox_status_deliver
  ON ground_outbox (status, deliver_after_utc);

-- ============================================================================
-- DEV 2: Sleep Architecture & Auscultation Recordings
-- ============================================================================

CREATE TABLE IF NOT EXISTS sleep_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  crew_id TEXT NOT NULL REFERENCES crew_members(id),
  mission_stage TEXT NOT NULL CHECK (mission_stage IN ('LAUNCH', 'MISSION', 'RETURN')),
  sleep_start_utc TEXT NOT NULL,
  sleep_end_utc TEXT NOT NULL,
  total_sleep_min INTEGER NOT NULL CHECK (total_sleep_min >= 0),
  time_in_bed_min INTEGER NOT NULL CHECK (time_in_bed_min > 0),
  sleep_score INTEGER NOT NULL CHECK (sleep_score BETWEEN 0 AND 100),
  sleep_efficiency_pct REAL NOT NULL CHECK (sleep_efficiency_pct BETWEEN 0 AND 100),
  deep_min INTEGER NOT NULL DEFAULT 0 CHECK (deep_min >= 0),
  rem_min INTEGER NOT NULL DEFAULT 0 CHECK (rem_min >= 0),
  light_min INTEGER NOT NULL DEFAULT 0 CHECK (light_min >= 0),
  awake_min INTEGER NOT NULL DEFAULT 0 CHECK (awake_min >= 0),
  recorded_at_utc TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_sleep_sessions_crew_start
  ON sleep_sessions (crew_id, sleep_start_utc DESC);

CREATE TABLE IF NOT EXISTS sleep_stages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES sleep_sessions(id) ON DELETE CASCADE,
  stage TEXT NOT NULL CHECK (stage IN ('DEEP', 'REM', 'LIGHT', 'AWAKE')),
  start_utc TEXT NOT NULL,
  end_utc TEXT NOT NULL,
  duration_min INTEGER NOT NULL CHECK (duration_min >= 0)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_sleep_stages_session
  ON sleep_stages (session_id, start_utc);

CREATE TABLE IF NOT EXISTS auscultation_recordings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  crew_id TEXT NOT NULL REFERENCES crew_members(id),
  mission_stage TEXT NOT NULL CHECK (mission_stage IN ('LAUNCH', 'MISSION', 'RETURN')),
  organ_type TEXT NOT NULL CHECK (organ_type IN ('CARDIAC', 'PULMONARY')),
  anatomical_site TEXT NOT NULL CHECK (anatomical_site IN (
    'aortic', 'pulmonic', 'tricuspid', 'mitral',
    'upper_left', 'upper_right', 'lower_left', 'lower_right'
  )),
  duration_sec INTEGER NOT NULL CHECK (duration_sec > 0 AND duration_sec <= 30),
  cabin_noise_dba REAL NOT NULL CHECK (cabin_noise_dba >= 0),
  file_rel_path TEXT NOT NULL UNIQUE,               -- e.g. 'audio/ID01_cardiac_mitral_20261114.webm'
  sha256_hex TEXT NOT NULL,
  findings_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(findings_json)),
  recorded_at_utc TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_auscultation_crew_ts
  ON auscultation_recordings (crew_id, recorded_at_utc DESC);

-- ============================================================================
-- DEV 3: Medical Wiki (FTS5), Psychology, Cognitive-Motor, Alerts,
--        Scheduled Checks, and AI Assisted Diagnoses
-- ============================================================================

CREATE TABLE IF NOT EXISTS wiki_articles (
  id TEXT PRIMARY KEY,
  category_en TEXT NOT NULL,
  title_en TEXT NOT NULL,
  drawer_code TEXT NOT NULL,                        -- e.g. 'DRAWER B2'
  steps_json TEXT NOT NULL CHECK (json_valid(steps_json)),
  escalation_en TEXT NOT NULL,
  source_diagnosis_id INTEGER,
  created_at_utc TEXT NOT NULL,
  updated_at_utc TEXT NOT NULL
) STRICT;

CREATE VIRTUAL TABLE IF NOT EXISTS wiki_articles_fts USING fts5(
  title_en,
  category_en,
  steps_json,
  content='wiki_articles',
  content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS trg_wiki_articles_ai
AFTER INSERT ON wiki_articles
BEGIN
  INSERT INTO wiki_articles_fts(rowid, title_en, category_en, steps_json)
  VALUES (new.rowid, new.title_en, new.category_en, new.steps_json);
END;

CREATE TRIGGER IF NOT EXISTS trg_wiki_articles_ad
AFTER DELETE ON wiki_articles
BEGIN
  INSERT INTO wiki_articles_fts(wiki_articles_fts, rowid, title_en, category_en, steps_json)
  VALUES ('delete', old.rowid, old.title_en, old.category_en, old.steps_json);
END;

CREATE TRIGGER IF NOT EXISTS trg_wiki_articles_au
AFTER UPDATE ON wiki_articles
BEGIN
  INSERT INTO wiki_articles_fts(wiki_articles_fts, rowid, title_en, category_en, steps_json)
  VALUES ('delete', old.rowid, old.title_en, old.category_en, old.steps_json);
  INSERT INTO wiki_articles_fts(rowid, title_en, category_en, steps_json)
  VALUES (new.rowid, new.title_en, new.category_en, new.steps_json);
END;

CREATE TABLE IF NOT EXISTS psych_tests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  crew_id TEXT NOT NULL REFERENCES crew_members(id),
  mission_stage TEXT NOT NULL CHECK (mission_stage IN ('LAUNCH', 'MISSION', 'RETURN')),
  mood_score INTEGER NOT NULL CHECK (mood_score BETWEEN 1 AND 5),
  stress_score INTEGER NOT NULL CHECK (stress_score BETWEEN 1 AND 5),
  loneliness_score INTEGER NOT NULL CHECK (loneliness_score BETWEEN 1 AND 5),
  motivation_score INTEGER NOT NULL CHECK (motivation_score BETWEEN 1 AND 5),
  wellbeing_index REAL NOT NULL CHECK (wellbeing_index BETWEEN 0 AND 100),
  notes_en TEXT,
  recorded_at_utc TEXT NOT NULL,
  mood_state TEXT CHECK (mood_state IS NULL OR mood_state IN ('CALM', 'FOCUSED', 'TIRED', 'STRESSED')),
  sleep_onset_utc TEXT,                             -- 'HH:MM' reported on screen 13
  wake_utc TEXT                                     -- 'HH:MM' reported on screen 13
) STRICT;

CREATE INDEX IF NOT EXISTS idx_psych_tests_crew_ts
  ON psych_tests (crew_id, recorded_at_utc DESC);

CREATE TABLE IF NOT EXISTS cognitive_tests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  crew_id TEXT NOT NULL REFERENCES crew_members(id),
  mission_stage TEXT NOT NULL CHECK (mission_stage IN ('LAUNCH', 'MISSION', 'RETURN')),
  test_type TEXT NOT NULL DEFAULT 'REACTION_ARENA',
  reaction_ms REAL NOT NULL CHECK (reaction_ms > 0),
  accuracy_pct REAL NOT NULL CHECK (accuracy_pct BETWEEN 0 AND 100),
  attention_score REAL NOT NULL CHECK (attention_score BETWEEN 0 AND 100),
  duration_sec INTEGER NOT NULL DEFAULT 120 CHECK (duration_sec > 0),
  recorded_at_utc TEXT NOT NULL,
  trials_total INTEGER NOT NULL DEFAULT 0 CHECK (trials_total >= 0),
  valid_responses INTEGER NOT NULL DEFAULT 0 CHECK (valid_responses >= 0),
  false_starts INTEGER NOT NULL DEFAULT 0 CHECK (false_starts >= 0),
  lapses INTEGER NOT NULL DEFAULT 0 CHECK (lapses >= 0)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_cognitive_tests_crew_ts
  ON cognitive_tests (crew_id, recorded_at_utc DESC);

CREATE TABLE IF NOT EXISTS scheduled_checks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  crew_id TEXT NOT NULL REFERENCES crew_members(id),
  check_type TEXT NOT NULL,
  title_en TEXT NOT NULL,
  due_at_utc TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'COMPLETED', 'DEFERRED', 'MISSED')),
  completed_at_utc TEXT,
  created_at_utc TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_scheduled_checks_crew_due
  ON scheduled_checks (crew_id, status, due_at_utc);

CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  crew_id TEXT NOT NULL REFERENCES crew_members(id),
  measurement_id INTEGER REFERENCES measurements(id),
  severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
  category TEXT NOT NULL,
  title_en TEXT NOT NULL,
  message_en TEXT NOT NULL,
  recommended_actions_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(recommended_actions_json)),
  wiki_article_id TEXT REFERENCES wiki_articles(id),
  is_quiet_deferred INTEGER NOT NULL DEFAULT 0 CHECK (is_quiet_deferred IN (0, 1)),
  acknowledged_at_utc TEXT,
  acknowledged_by TEXT REFERENCES crew_members(id),
  created_at_utc TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_alerts_crew_ack
  ON alerts (crew_id, acknowledged_at_utc, created_at_utc DESC);

CREATE TABLE IF NOT EXISTS diagnoses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  crew_id TEXT NOT NULL REFERENCES crew_members(id),
  mission_stage TEXT NOT NULL CHECK (mission_stage IN ('LAUNCH', 'MISSION', 'RETURN')),
  anomaly_score REAL NOT NULL CHECK (anomaly_score >= 0),
  is_anomaly INTEGER NOT NULL CHECK (is_anomaly IN (0, 1)),
  model_name TEXT NOT NULL,
  llm_summary_en TEXT NOT NULL,
  preventive_steps_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(preventive_steps_json)),
  cited_article_ids_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(cited_article_ids_json)),
  validation_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (validation_status IN (
    'PENDING_REVIEW', 'APPROVED', 'REJECTED', 'PROMOTED_TO_GUIDE'
  )),
  validated_by TEXT REFERENCES crew_members(id),
  validated_at_utc TEXT,
  physician_notes_en TEXT,
  created_at_utc TEXT NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_diagnoses_crew_status
  ON diagnoses (crew_id, validation_status, created_at_utc DESC);
