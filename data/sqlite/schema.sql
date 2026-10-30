-- =====================================================================
-- Warehouse Environmental Monitoring & Risk Traceability System Schema
-- =====================================================================

PRAGMA foreign_keys = ON;

-- 1. Warehouses Master Table
CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id VARCHAR(16) PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    region VARCHAR(64) NOT NULL,
    address VARCHAR(256) NOT NULL,
    total_zones INTEGER NOT NULL,
    operational_status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP NOT NULL
);

-- 2. Storage Requirements Catalog
CREATE TABLE IF NOT EXISTS storage_requirements (
    requirement_id VARCHAR(32) PRIMARY KEY,
    profile_name VARCHAR(128) NOT NULL,
    allowed_zone_types VARCHAR(256) NOT NULL,
    temp_crit_min_c REAL NOT NULL,
    temp_warn_min_c REAL NOT NULL,
    temp_warn_max_c REAL NOT NULL,
    temp_crit_max_c REAL NOT NULL,
    humidity_crit_min_pct REAL NOT NULL,
    humidity_crit_max_pct REAL NOT NULL,
    max_excursion_duration_min INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'
);

-- 3. Zones Master Table
CREATE TABLE IF NOT EXISTS zones (
    zone_id VARCHAR(32) PRIMARY KEY,
    warehouse_id VARCHAR(16) NOT NULL,
    zone_name VARCHAR(128) NOT NULL,
    zone_type VARCHAR(64) NOT NULL,
    target_temp_c REAL NOT NULL,
    temp_min_c REAL NOT NULL,
    temp_max_c REAL NOT NULL,
    target_humidity_pct REAL NOT NULL,
    humidity_min_pct REAL NOT NULL,
    humidity_max_pct REAL NOT NULL,
    max_occupancy INTEGER NOT NULL,
    max_door_open_sec INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id) ON DELETE CASCADE
);

-- 4. Sensors Master Table
CREATE TABLE IF NOT EXISTS sensors (
    sensor_id VARCHAR(64) PRIMARY KEY,
    zone_id VARCHAR(32) NOT NULL,
    sensor_type VARCHAR(32) NOT NULL,
    model_number VARCHAR(64) NOT NULL,
    calibration_date DATE NOT NULL,
    calibration_due DATE NOT NULL,
    battery_level_pct REAL NOT NULL,
    drift_offset REAL NOT NULL DEFAULT 0.0,
    status VARCHAR(32) NOT NULL DEFAULT 'ONLINE',
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id) ON DELETE CASCADE
);

-- 5. Sensor Readings Time-Series Table
CREATE TABLE IF NOT EXISTS sensor_readings (
    reading_id VARCHAR(96) PRIMARY KEY,
    sensor_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    metric_type VARCHAR(32) NOT NULL,
    raw_value REAL NOT NULL,
    calibrated_value REAL NOT NULL,
    unit VARCHAR(16) NOT NULL,
    status_code VARCHAR(32) NOT NULL DEFAULT 'NORMAL',
    FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id) ON DELETE CASCADE
);

-- 6. Door Events Table
CREATE TABLE IF NOT EXISTS door_events (
    door_event_id VARCHAR(64) PRIMARY KEY,
    zone_id VARCHAR(32) NOT NULL,
    door_identifier VARCHAR(32) NOT NULL,
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP NOT NULL,
    duration_sec INTEGER NOT NULL,
    is_ajar_violation BOOLEAN NOT NULL DEFAULT 0,
    actor VARCHAR(64) NOT NULL,
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id) ON DELETE CASCADE
);

-- 7. Inventory Lots Master Table
CREATE TABLE IF NOT EXISTS inventory_lots (
    lot_id VARCHAR(32) PRIMARY KEY,
    product_code VARCHAR(64) NOT NULL,
    requirement_id VARCHAR(32) NOT NULL,
    zone_id VARCHAR(32) NOT NULL,
    arrival_time TIMESTAMP NOT NULL,
    departure_time TIMESTAMP,
    dwell_hours REAL NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price_usd REAL NOT NULL,
    total_value_usd REAL NOT NULL,
    lifecycle_state VARCHAR(32) NOT NULL DEFAULT 'STORED',
    FOREIGN KEY (requirement_id) REFERENCES storage_requirements(requirement_id),
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id)
);

-- 8. Alarms Table
CREATE TABLE IF NOT EXISTS alarms (
    alarm_id VARCHAR(64) PRIMARY KEY,
    zone_id VARCHAR(32) NOT NULL,
    sensor_id VARCHAR(64),
    door_event_id VARCHAR(64),
    alarm_type VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_minutes REAL,
    trigger_value REAL NOT NULL,
    threshold_limit REAL NOT NULL,
    peak_excursion REAL,
    affected_lot_count INTEGER NOT NULL DEFAULT 0,
    total_loss_usd REAL NOT NULL DEFAULT 0.0,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    FOREIGN KEY (zone_id) REFERENCES zones(zone_id),
    FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id),
    FOREIGN KEY (door_event_id) REFERENCES door_events(door_event_id)
);

-- 9. Alarm Affected Lots Bridge Table
CREATE TABLE IF NOT EXISTS alarm_affected_lots (
    bridge_id VARCHAR(96) PRIMARY KEY,
    alarm_id VARCHAR(64) NOT NULL,
    lot_id VARCHAR(32) NOT NULL,
    overlap_start TIMESTAMP NOT NULL,
    overlap_end TIMESTAMP NOT NULL,
    exposure_hours REAL NOT NULL,
    degree_hours REAL NOT NULL,
    risk_category VARCHAR(32) NOT NULL,
    disposition_status VARCHAR(32) NOT NULL DEFAULT 'IDENTIFIED',
    FOREIGN KEY (alarm_id) REFERENCES alarms(alarm_id) ON DELETE CASCADE,
    FOREIGN KEY (lot_id) REFERENCES inventory_lots(lot_id) ON DELETE CASCADE
);

-- 10. Inspections Table
CREATE TABLE IF NOT EXISTS inspections (
    inspection_id VARCHAR(80) PRIMARY KEY,
    alarm_id VARCHAR(64) NOT NULL,
    inspector_role VARCHAR(32) NOT NULL,
    inspector_id VARCHAR(32) NOT NULL,
    inspection_time TIMESTAMP NOT NULL,
    findings TEXT NOT NULL,
    physical_damage BOOLEAN NOT NULL DEFAULT 0,
    recommended_action VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'COMPLETED',
    FOREIGN KEY (alarm_id) REFERENCES alarms(alarm_id)
);

-- 11. Remediations Table
CREATE TABLE IF NOT EXISTS remediations (
    remediation_id VARCHAR(96) PRIMARY KEY,
    inspection_id VARCHAR(80) NOT NULL,
    action_type VARCHAR(64) NOT NULL,
    lot_id VARCHAR(32),
    sensor_id VARCHAR(64),
    executed_by VARCHAR(64) NOT NULL,
    approved_by VARCHAR(64) NOT NULL,
    completed_at TIMESTAMP NOT NULL,
    financial_impact_usd REAL NOT NULL DEFAULT 0.0,
    status VARCHAR(32) NOT NULL DEFAULT 'VERIFIED',
    FOREIGN KEY (inspection_id) REFERENCES inspections(inspection_id),
    FOREIGN KEY (lot_id) REFERENCES inventory_lots(lot_id),
    FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
);

-- 12. Ground Truth Anomalies Table (Separated from baseline operational queries)
CREATE TABLE IF NOT EXISTS ground_truth (
    anomaly_id VARCHAR(32) PRIMARY KEY,
    issue_type VARCHAR(64) NOT NULL,
    entity_type VARCHAR(32) NOT NULL,
    entity_id VARCHAR(96) NOT NULL,
    zone_id VARCHAR(32) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    expected_detection BOOLEAN NOT NULL DEFAULT 1,
    expected_alarm_type VARCHAR(64),
    expected_severity VARCHAR(16) NOT NULL,
    rationale TEXT NOT NULL
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_ts ON sensor_readings(sensor_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_ts ON sensor_readings(timestamp);
CREATE INDEX IF NOT EXISTS idx_inventory_lots_zone_arrival ON inventory_lots(zone_id, arrival_time);
CREATE INDEX IF NOT EXISTS idx_alarms_zone_start ON alarms(zone_id, start_time);
CREATE INDEX IF NOT EXISTS idx_door_events_zone ON door_events(zone_id, opened_at);
CREATE INDEX IF NOT EXISTS idx_alarm_affected_lots_alarm ON alarm_affected_lots(alarm_id);
CREATE INDEX IF NOT EXISTS idx_alarm_affected_lots_lot ON alarm_affected_lots(lot_id);
