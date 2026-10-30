# Data Dictionary: Warehouse Environmental Monitoring & Risk Traceability System

This document provides the canonical schema definition and data dictionary for the end-to-end multi-zone warehouse environmental monitoring, risk condition detection, and inventory traceability solution.

---

## 1. Entity-Relationship Overview

| Entity | Primary Key | Foreign Keys | Cardinality / Relationships | Lifecycle States |
| :--- | :--- | :--- | :--- | :--- |
| **Warehouse** | `warehouse_id` | *None* | 1:N with Zone | `ACTIVE`, `MAINTENANCE`, `DECOMMISSIONED` |
| **Zone** | `zone_id` | `warehouse_id` | N:1 Warehouse; 1:N Sensors; 1:N DoorEvents; 1:N Alarms; 1:N InventoryLots | `ACTIVE`, `INACTIVE`, `CLEANING`, `QUARANTINE` |
| **StorageRequirement** | `requirement_id` | *None* | 1:N with InventoryLot | `ACTIVE`, `SUPERSEDED`, `DEPRECATED` |
| **Sensor** | `sensor_id` | `zone_id` | N:1 Zone; 1:N SensorReadings | `ONLINE`, `OFFLINE`, `CALIBRATING`, `FAULTY` |
| **SensorReading** | `reading_id` | `sensor_id` | N:1 Sensor | `NORMAL`, `EXCURSION`, `SUSPECT`, `CALIBRATION` |
| **DoorEvent** | `door_event_id` | `zone_id` | N:1 Zone | `NORMAL`, `AJAR_WARNING`, `AJAR_CRITICAL` |
| **InventoryLot** | `lot_id` | `zone_id`, `requirement_id` | N:1 Zone, N:1 StorageRequirement; N:M with Alarm | `RECEIVED`, `STORED`, `QUARANTINED`, `RELEASED`, `CONDEMNED` |
| **Alarm** | `alarm_id` | `zone_id`, `sensor_id` (opt), `door_event_id` (opt) | N:1 Zone, 1:N Inspections; N:M with InventoryLot | `ACTIVE`, `ACKNOWLEDGED`, `INSPECTING`, `RESOLVED`, `CLOSED` |
| **AlarmAffectedLot** | `bridge_id` | `alarm_id`, `lot_id` | Bridge N:M between Alarm and InventoryLot | `IDENTIFIED`, `ASSESSED`, `CLEARED`, `REMEDIATED` |
| **Inspection** | `inspection_id` | `alarm_id` | N:1 Alarm; 1:N Remediations | `SCHEDULED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED` |
| **Remediation** | `remediation_id` | `inspection_id`, `lot_id` (opt), `sensor_id` (opt) | N:1 Inspection | `PLANNED`, `IN_PROGRESS`, `EXECUTED`, `VERIFIED` |

---

## 2. Table Specifications and Field Data Dictionary

### 2.1 Warehouse (`warehouses`)
Master record for individual storage facilities.
- **Primary Key:** `warehouse_id`
- **Naming Convention:** `WH-001`, `WH-002`, ...

| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `warehouse_id` | `VARCHAR(16)` | Required | Regex `^WH-\d{3}$` | N/A | Unique (PK) | Must match `WH-` followed by 3 digits |
| `name` | `VARCHAR(128)` | Required | Free text | N/A | Non-unique | Length between 3 and 128 characters |
| `region` | `VARCHAR(64)` | Required | `NA-EAST`, `NA-WEST`, `EU-CENTRAL`, `APAC-SOUTH`, `APAC-EAST` | N/A | Non-unique | Must belong to approved operational regions |
| `address` | `VARCHAR(256)` | Required | Free text | N/A | Non-unique | Valid postal address format |
| `total_zones` | `INTEGER` | Required | `1 <= total_zones <= 50` | Count | Non-unique | Must match count of linked zones |
| `operational_status` | `VARCHAR(32)` | Required | `ACTIVE`, `MAINTENANCE`, `DECOMMISSIONED` | N/A | Non-unique | Valid lifecycle state |
| `created_at` | `TIMESTAMP` | Required | ISO-8601 UTC timestamp | UTC | Non-unique | Cannot be in future |

---

### 2.2 Zone (`zones`)
Micro-climate and physical partitioning within a warehouse facility.
- **Primary Key:** `zone_id`
- **Foreign Key:** `warehouse_id` REFERENCES `warehouses(warehouse_id)`
- **Naming Convention:** `ZONE-<warehouse-id>-001` (e.g., `ZONE-WH-001-001`)

| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `zone_id` | `VARCHAR(32)` | Required | Regex `^ZONE-WH-\d{3}-\d{3}$` | N/A | Unique (PK) | Must incorporate parent warehouse ID |
| `warehouse_id` | `VARCHAR(16)` | Required | Valid `warehouse_id` | N/A | Non-unique (FK) | Must exist in `warehouses` |
| `zone_name` | `VARCHAR(128)` | Required | Free text | N/A | Non-unique | Descriptive room/aisle name |
| `zone_type` | `VARCHAR(64)` | Required | `ULTRA_LOW_FREEZE`, `COLD_STORAGE`, `CONTROLLED_ROOM_TEMP`, `AMBIENT`, `HUMIDITY_CONTROLLED`, `LOADING_DOCK`, `QUARANTINE_HOLD` | N/A | Non-unique | Must belong to approved zone types |
| `target_temp_c` | `FLOAT` | Required | `-80.0 <= target_temp_c <= 40.0` | Celsius (°C) | Non-unique | Must match thermal type envelope |
| `temp_min_c` | `FLOAT` | Required | `temp_min_c < target_temp_c` | Celsius (°C) | Non-unique | Lower baseline tolerance limit |
| `temp_max_c` | `FLOAT` | Required | `temp_max_c > target_temp_c` | Celsius (°C) | Non-unique | Upper baseline tolerance limit |
| `target_humidity_pct`| `FLOAT` | Required | `10.0 <= target_humidity_pct <= 95.0` | % RH | Non-unique | Relative humidity target |
| `humidity_min_pct` | `FLOAT` | Required | `humidity_min_pct < target_humidity_pct` | % RH | Non-unique | Lower humidity limit |
| `humidity_max_pct` | `FLOAT` | Required | `humidity_max_pct > target_humidity_pct` | % RH | Non-unique | Upper humidity limit |
| `max_occupancy` | `INTEGER` | Required | `0 <= max_occupancy <= 100` | Persons | Non-unique | Max simultaneous workers allowed |
| `max_door_open_sec` | `INTEGER` | Required | `30 <= max_door_open_sec <= 3600` | Seconds | Non-unique | Seconds before door ajar alarm fires |
| `status` | `VARCHAR(32)` | Required | `ACTIVE`, `INACTIVE`, `CLEANING`, `QUARANTINE` | N/A | Non-unique | Lifecycle state |

---

### 2.3 StorageRequirement (`storage_requirements`)
Regulatory or client quality profile specified for perishable products/lots.
- **Primary Key:** `requirement_id`
- **Naming Convention:** `REQ-<PROFILE_CODE>` (e.g., `REQ-VACCINE-ULTRA`, `REQ-PHARMA-COLD`, `REQ-PERISHABLE-FRESH`, `REQ-DRY-AMBIENT`)

| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `requirement_id` | `VARCHAR(32)` | Required | Regex `^REQ-[A-Z0-9_-]+$` | N/A | Unique (PK) | Alphanumeric profile code |
| `profile_name` | `VARCHAR(128)` | Required | Descriptive name | N/A | Non-unique | E.g. "Cold-Chain Biologics (+2 to +8 C)" |
| `allowed_zone_types` | `VARCHAR(256)` | Required | Comma-separated zone types | N/A | Non-unique | Incompatible if placed outside these |
| `temp_crit_min_c` | `FLOAT` | Required | `-85.0 to 35.0` | Celsius (°C) | Non-unique | `temp_crit_min_c <= temp_warn_min_c` |
| `temp_warn_min_c` | `FLOAT` | Required | `-80.0 to 38.0` | Celsius (°C) | Non-unique | Warning lower bound |
| `temp_warn_max_c` | `FLOAT` | Required | `-75.0 to 42.0` | Celsius (°C) | Non-unique | Warning upper bound |
| `temp_crit_max_c` | `FLOAT` | Required | `-70.0 to 45.0` | Celsius (°C) | Non-unique | `temp_crit_max_c >= temp_warn_max_c` |
| `humidity_crit_min_pct`| `FLOAT` | Required | `5.0 to 80.0` | % RH | Non-unique | Lower critical humidity |
| `humidity_crit_max_pct`| `FLOAT` | Required | `20.0 to 98.0` | % RH | Non-unique | Upper critical humidity |
| `max_excursion_duration_min` | `INTEGER` | Required | `1 to 1440` | Minutes | Non-unique | Max cumulative allowable breach before condemnation |
| `status` | `VARCHAR(32)` | Required | `ACTIVE`, `SUPERSEDED`, `DEPRECATED` | N/A | Non-unique | Regulatory lifecycle status |

---

### 2.4 Sensor (`sensors`)
Physical environmental telemetry sensor deployed in a zone.
- **Primary Key:** `sensor_id`
- **Foreign Key:** `zone_id` REFERENCES `zones(zone_id)`
- **Naming Convention:** `SNS-<zone-id>-<TYPE>-<INDEX>` (e.g., `SNS-ZONE-WH-001-001-TEMP-01`)

| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `sensor_id` | `VARCHAR(64)` | Required | Regex `^SNS-ZONE-[A-Z0-9-]+-(TEMP\|HUM\|OCC)-\d{2}$` | N/A | Unique (PK) | Must include zone ID and sensor type |
| `zone_id` | `VARCHAR(32)` | Required | Valid `zone_id` | N/A | Non-unique (FK) | Must exist in `zones` |
| `sensor_type` | `VARCHAR(32)` | Required | `TEMPERATURE`, `HUMIDITY`, `OCCUPANCY` | N/A | Non-unique | Target metric |
| `model_number` | `VARCHAR(64)` | Required | E.g. `SENS-T2000`, `HUMID-S50`, `PIR-OCC-10` | N/A | Non-unique | Hardware model number |
| `calibration_date` | `DATE` | Required | ISO-8601 Date (`YYYY-MM-DD`) | Date | Non-unique | Must be `<= CURRENT_DATE` |
| `calibration_due` | `DATE` | Required | ISO-8601 Date (`YYYY-MM-DD`) | Date | Non-unique | Must be `> calibration_date` |
| `battery_level_pct` | `FLOAT` | Required | `0.0 <= battery_level_pct <= 100.0` | % | Non-unique | Current battery level |
| `drift_offset` | `FLOAT` | Required | `-5.0 to +5.0` | Metric unit | Non-unique | Calibration drift offset |
| `status` | `VARCHAR(32)` | Required | `ONLINE`, `OFFLINE`, `CALIBRATING`, `FAULTY` | N/A | Non-unique | Sensor lifecycle status |

---

### 2.5 SensorReading (`sensor_readings`)
High-frequency periodic telemetry observations.
- **Primary Key:** `reading_id`
- **Foreign Key:** `sensor_id` REFERENCES `sensors(sensor_id)`
- **Naming Convention:** `RDG-<sensor-id>-<timestamp>` (e.g. `RDG-SNS-ZONE-WH-001-001-TEMP-01-20261022T080000Z`)

| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `reading_id` | `VARCHAR(96)` | Required | Regex `^RDG-SNS-.*-\d{8}T\d{6}Z$` | N/A | Unique (PK) | Deterministic composite ID |
| `sensor_id` | `VARCHAR(64)` | Required | Valid `sensor_id` | N/A | Non-unique (FK) | Must exist in `sensors` |
| `timestamp` | `TIMESTAMP` | Required | ISO-8601 UTC timestamp | UTC | Non-unique | Monotonically ascending per sensor |
| `metric_type` | `VARCHAR(32)` | Required | `TEMPERATURE`, `HUMIDITY`, `OCCUPANCY` | N/A | Non-unique | Must match parent sensor type |
| `raw_value` | `FLOAT` | Required | Physical sensor float reading | °C, % RH, Count | Non-unique | Unadjusted hardware reading |
| `calibrated_value`| `FLOAT` | Required | `raw_value - drift_offset` | °C, % RH, Count | Non-unique | Reconciled value |
| `unit` | `VARCHAR(16)` | Required | `CELSIUS`, `PERCENT_RH`, `PERSON_COUNT` | N/A | Non-unique | Unit of calibrated value |
| `status_code` | `VARCHAR(32)` | Required | `NORMAL`, `EXCURSION`, `SUSPECT`, `CALIBRATION` | N/A | Non-unique | Telemetry health flag |

---

### 2.6 DoorEvent (`door_events`)
Records physical ingress/egress door open and close cycles.
- **Primary Key:** `door_event_id`
- **Foreign Key:** `zone_id` REFERENCES `zones(zone_id)`
- **Naming Convention:** `DOOR-<zone-id>-<DOOR_NUM>-<timestamp>`

| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `door_event_id` | `VARCHAR(64)` | Required | Regex `^DOOR-ZONE-.*-D\d{2}-\d{8}T\d{6}Z$` | N/A | Unique (PK) | Deterministic event identifier |
| `zone_id` | `VARCHAR(32)` | Required | Valid `zone_id` | N/A | Non-unique (FK) | Must exist in `zones` |
| `door_identifier` | `VARCHAR(32)` | Required | E.g. `DOOR-D01`, `DOOR-D02` | N/A | Non-unique | Door identifier within zone |
| `opened_at` | `TIMESTAMP` | Required | ISO-8601 UTC timestamp | UTC | Non-unique | Door opened timestamp |
| `closed_at` | `TIMESTAMP` | Required | ISO-8601 UTC timestamp | UTC | Non-unique | Must be `>= opened_at` |
| `duration_sec` | `INTEGER` | Required | `>= 0` | Seconds | Non-unique | Reconciles to `closed_at - opened_at` |
| `is_ajar_violation`| `BOOLEAN` | Required | `TRUE`, `FALSE` | Boolean | Non-unique | `TRUE` if `duration_sec > max_door_open_sec` |
| `actor` | `VARCHAR(64)` | Required | Operator or Badge ID | N/A | Non-unique | Plant operator or automated AGV |

---

### 2.7 InventoryLot (`inventory_lots`)
Stored commercial product lots dwelling inside warehouse zones.
- **Primary Key:** `lot_id`
- **Foreign Keys:** `zone_id` REFERENCES `zones(zone_id)`, `requirement_id` REFERENCES `storage_requirements(requirement_id)`
- **Naming Convention:** `LOT-2026-000001` (zero-padded 6 digits)

| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `lot_id` | `VARCHAR(32)` | Required | Regex `^LOT-2026-\d{6}$` | N/A | Unique (PK) | Sequential zero-padded lot ID |
| `product_code` | `VARCHAR(64)` | Required | E.g. `MED-BIOLOGIC-902`, `FOOD-DAIRY-102` | N/A | Non-unique | Stock Keeping Unit / SKU |
| `requirement_id` | `VARCHAR(32)` | Required | Valid `requirement_id` | N/A | Non-unique (FK) | Must exist in `storage_requirements` |
| `zone_id` | `VARCHAR(32)` | Required | Valid `zone_id` | N/A | Non-unique (FK) | Must exist in `zones` |
| `arrival_time` | `TIMESTAMP` | Required | ISO-8601 UTC timestamp | UTC | Non-unique | Dwell start time |
| `departure_time` | `TIMESTAMP` | Optional | ISO-8601 UTC timestamp or `NULL` | UTC | Non-unique | If not null, `>= arrival_time` |
| `dwell_hours` | `FLOAT` | Required | `>= 0.0` | Hours | Non-unique | Calculated dwell duration |
| `quantity` | `INTEGER` | Required | `1 <= quantity <= 10000` | Units/Packs | Non-unique | Physical inventory quantity |
| `unit_price_usd` | `FLOAT` | Required | `0.50 <= unit_price_usd <= 5000.0` | USD ($) | Non-unique | Price per unit |
| `total_value_usd`| `FLOAT` | Required | `quantity * unit_price_usd` | USD ($) | Non-unique | Reconciled total monetary valuation |
| `lifecycle_state`| `VARCHAR(32)` | Required | `RECEIVED`, `STORED`, `QUARANTINED`, `RELEASED`, `CONDEMNED` | N/A | Non-unique | Current inventory status |

---

### 2.8 Alarm (`alarms`)
Actionable alert generated when risk conditions or threshold breaches occur.
- **Primary Key:** `alarm_id`
- **Foreign Keys:** `zone_id` REFERENCES `zones(zone_id)`, `sensor_id` (Opt), `door_event_id` (Opt)
- **Naming Convention:** `ALM-<zone-id>-<timestamp>`

| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `alarm_id` | `VARCHAR(64)` | Required | Regex `^ALM-ZONE-.*-\d{8}T\d{6}Z$` | N/A | Unique (PK) | Deterministic alarm identifier |
| `zone_id` | `VARCHAR(32)` | Required | Valid `zone_id` | N/A | Non-unique (FK) | Must exist in `zones` |
| `sensor_id` | `VARCHAR(64)` | Optional | Valid `sensor_id` or `NULL` | N/A | Non-unique (FK) | Sensor initiating the alarm |
| `door_event_id` | `VARCHAR(64)` | Optional | Valid `door_event_id` or `NULL`| N/A | Non-unique (FK) | Door event causing alarm |
| `alarm_type` | `VARCHAR(64)` | Required | `TEMP_EXCURSION_HIGH`, `TEMP_EXCURSION_LOW`, `HUMIDITY_HIGH`, `HUMIDITY_LOW`, `DOOR_AJAR_EXTENDED`, `SENSOR_OUTAGE_GAP`, `SENSOR_DRIFT_EXCESSIVE`, `OCCUPANCY_EXCEEDED` | N/A | Non-unique | Standard risk taxonomy |
| `severity` | `VARCHAR(16)` | Required | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` | N/A | Non-unique | Risk rating matrix |
| `start_time` | `TIMESTAMP` | Required | ISO-8601 UTC timestamp | UTC | Non-unique | Excursion or outage start |
| `end_time` | `TIMESTAMP` | Optional | ISO-8601 UTC timestamp or `NULL` | UTC | Non-unique | Must be `>= start_time` |
| `duration_minutes` | `FLOAT` | Optional | `>= 0.0` | Minutes | Non-unique | `(end_time - start_time) / 60` |
| `trigger_value` | `FLOAT` | Required | Observed value | °C, % RH, Sec | Non-unique | Value triggering alarm |
| `threshold_limit`| `FLOAT` | Required | Breached boundary | °C, % RH, Sec | Non-unique | Configured zone/product limit |
| `peak_excursion` | `FLOAT` | Optional | Maximum deviation | °C, % RH | Non-unique | Peak severity during window |
| `affected_lot_count` | `INTEGER`| Required | `>= 0` | Count | Non-unique | Reconciles to count in `alarm_affected_lots` |
| `total_loss_usd` | `FLOAT` | Required | `>= 0.0` | USD ($) | Non-unique | Sum of damages/condemned lots |
| `status` | `VARCHAR(32)` | Required | `ACTIVE`, `ACKNOWLEDGED`, `INSPECTING`, `RESOLVED`, `CLOSED` | N/A | Non-unique | Alarm lifecycle transition |

---

### 2.9 AlarmAffectedLot (`alarm_affected_lots`)
Bridge table linking Alarms to specific Inventory Lots based on spatiotemporal overlap.
- **Primary Key:** `bridge_id`
- **Foreign Keys:** `alarm_id` REFERENCES `alarms(alarm_id)`, `lot_id` REFERENCES `inventory_lots(lot_id)`
- **Naming Convention:** `AFL-<alarm-id>-<lot-id>`

| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `bridge_id` | `VARCHAR(96)` | Required | Regex `^AFL-ALM-.*-LOT-.*$` | N/A | Unique (PK) | Composite bridge identifier |
| `alarm_id` | `VARCHAR(64)` | Required | Valid `alarm_id` | N/A | Non-unique (FK) | Must exist in `alarms` |
| `lot_id` | `VARCHAR(32)` | Required | Valid `lot_id` | N/A | Non-unique (FK) | Must exist in `inventory_lots` |
| `overlap_start` | `TIMESTAMP` | Required | `max(alarm.start_time, lot.arrival_time)` | UTC | Non-unique | Exposure start |
| `overlap_end` | `TIMESTAMP` | Required | `min(alarm.end_time, lot.departure_time)` | UTC | Non-unique | Exposure end (`>= overlap_start`) |
| `exposure_hours` | `FLOAT` | Required | `(overlap_end - overlap_start) / 3600` | Hours | Non-unique | Active exposure duration |
| `degree_hours` | `FLOAT` | Required | `integral( |T(t) - T_limit| dt )` | °C·Hours | Non-unique | Thermal dosage calculation |
| `risk_category` | `VARCHAR(32)` | Required | `LOW_RISK`, `MODERATE_EXPOSURE`, `CRITICAL_VIOLATION` | N/A | Non-unique | Risk classification |
| `disposition_status` | `VARCHAR(32)`| Required | `IDENTIFIED`, `ASSESSED`, `CLEARED`, `REMEDIATED` | N/A | Non-unique | Lot mitigation status |

---

### 2.10 Inspection (`inspections`)
Physical or sensor QA evaluation triggered by alarms or preventive maintenance.
- **Primary Key:** `inspection_id`
- **Foreign Key:** `alarm_id` REFERENCES `alarms(alarm_id)`
- **Naming Convention:** `INS-<alarm-id>-01`

| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `inspection_id` | `VARCHAR(80)` | Required | Regex `^INS-ALM-.*-\d{2}$` | N/A | Unique (PK) | Unique inspection record |
| `alarm_id` | `VARCHAR(64)` | Required | Valid `alarm_id` | N/A | Non-unique (FK) | Must exist in `alarms` |
| `inspector_role` | `VARCHAR(32)` | Required | `MAINTENANCE_ENGINEER`, `QUALITY_ENGINEER`, `PLANT_OPERATOR` | N/A | Non-unique | Assigned actor role |
| `inspector_id` | `VARCHAR(32)` | Required | E.g. `TECH-441`, `QA-902` | N/A | Non-unique | Employee ID |
| `inspection_time`| `TIMESTAMP` | Required | ISO-8601 UTC timestamp | UTC | Non-unique | `>= alarm.start_time` |
| `findings` | `TEXT` | Required | Descriptive findings report | N/A | Non-unique | Physical inspection observations |
| `physical_damage`| `BOOLEAN` | Required | `TRUE`, `FALSE` | Boolean | Non-unique | Condensation, thawing, seal broken |
| `recommended_action`| `VARCHAR(64)`| Required | `RELEASE`, `SAMPLE_TEST`, `QUARANTINE_LOT`, `CONDEMN_LOT`, `REPLACE_SENSOR`, `HVAC_SERVICE` | N/A | Non-unique | Recommended disposition |
| `status` | `VARCHAR(32)` | Required | `SCHEDULED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED` | N/A | Non-unique | Lifecycle state |

---

### 2.11 Remediation (`remediations`)
Corrective, preventative, and inventory disposition actions executed in response to inspections.
- **Primary Key:** `remediation_id`
- **Foreign Keys:** `inspection_id` REFERENCES `inspections(inspection_id)`, `lot_id` (Opt), `sensor_id` (Opt)
- **Naming Convention:** `REM-<inspection-id>-01`

| Field Name | Type | Req/Opt | Allowed Values | Units | Uniqueness | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `remediation_id` | `VARCHAR(96)` | Required | Regex `^REM-INS-.*-\d{2}$` | N/A | Unique (PK) | Unique remediation record |
| `inspection_id` | `VARCHAR(80)` | Required | Valid `inspection_id` | N/A | Non-unique (FK) | Must exist in `inspections` |
| `action_type` | `VARCHAR(64)` | Required | `LOT_QUARANTINE`, `LOT_CONDEMNATION`, `LOT_RELEASED_WITH_VARIANCE`, `SENSOR_REPLACEMENT`, `SENSOR_RECALIBRATION`, `DOOR_SEAL_REPAIR`, `HVAC_COMPRESSOR_RESTART` | N/A | Non-unique | Specific remediation action |
| `lot_id` | `VARCHAR(32)` | Optional | Valid `lot_id` or `NULL` | N/A | Non-unique (FK) | Lot being remediated |
| `sensor_id` | `VARCHAR(64)` | Optional | Valid `sensor_id` or `NULL` | N/A | Non-unique (FK) | Sensor being serviced |
| `executed_by` | `VARCHAR(64)` | Required | Staff badge ID / name | N/A | Non-unique | Actor performing remediation |
| `approved_by` | `VARCHAR(64)` | Required | Quality / Plant supervisor | N/A | Non-unique | Dual sign-off requirement |
| `completed_at` | `TIMESTAMP` | Required | ISO-8601 UTC timestamp | UTC | Non-unique | `>= inspection.inspection_time` |
| `financial_impact_usd` | `FLOAT`| Required | `>= 0.0` | USD ($) | Non-unique | Scrap loss, repair cost, or rework |
| `status` | `VARCHAR(32)` | Required | `PLANNED`, `IN_PROGRESS`, `EXECUTED`, `VERIFIED` | N/A | Non-unique | Execution lifecycle status |

---

## 3. Ground Truth Data Dictionary (`ground_truth`)

The ground truth dataset documents all intentional synthetic anomalies, excursions, sensor failures, and deliberate data irregularities injected into the environment. It is stored separately in `ground_truth.csv` and `ground_truth.json` and must **never** be leaked into input feature sets for monitoring models.

| Field Name | Type | Req/Opt | Allowed Values | Units | Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `anomaly_id` | `VARCHAR(32)` | Required | Regex `^ANOM-\d{5}$` | N/A | Deterministic unique anomaly identifier |
| `issue_type` | `VARCHAR(64)` | Required | `INCOMPATIBLE_ZONE_ASSIGNMENT`, `AMBIGUOUS_SENSOR_ZONE_MAPPING`, `SILENT_SENSOR_OUTAGE_GAP`, `UNLINKED_ALARM_AFFECTED_LOTS`, `SENSOR_DRIFT_EXCESSIVE`, `THERMAL_EXCURSION_CHILLER_FAIL`, `DOOR_AJAR_CONDENSATION` | N/A | Standard ground truth anomaly taxonomy |
| `entity_type` | `VARCHAR(32)` | Required | `InventoryLot`, `Sensor`, `SensorReading`, `Alarm`, `Zone` | N/A | Affected entity domain |
| `entity_id` | `VARCHAR(96)` | Required | Valid ID matching `entity_type` | N/A | Target entity identifier |
| `zone_id` | `VARCHAR(32)` | Required | Valid `zone_id` | N/A | Primary zone location |
| `start_time` | `TIMESTAMP` | Required | ISO-8601 UTC timestamp | UTC | Anomaly onset |
| `end_time` | `TIMESTAMP` | Required | ISO-8601 UTC timestamp | UTC | `>= start_time` |
| `expected_detection` | `BOOLEAN` | Required | `TRUE`, `FALSE` | Boolean | Whether an automated system should detect |
| `expected_alarm_type`| `VARCHAR(64)`| Optional | Corresponding expected alarm | N/A | Expected alarm classification |
| `expected_severity` | `VARCHAR(16)` | Required | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` | N/A | Ground truth impact rating |
| `rationale` | `TEXT` | Required | Explanatory ground truth description | N/A | Engineering explanation of anomaly |

---

## 4. Foreign Key and Referential Integrity Rules

1. Every `Zone` must link to an existing `Warehouse`.
2. Every `Sensor` must link to an existing `Zone`.
3. Every `SensorReading` must link to an existing `Sensor` with metric type matching sensor specifications.
4. Every `DoorEvent` must link to an existing `Zone`.
5. Every `InventoryLot` must link to an existing `StorageRequirement` and `Zone`.
6. Every `Alarm` must link to an existing `Zone`, and optional sensor or door event.
7. Every record in `AlarmAffectedLot` must link an existing `Alarm` and an existing `InventoryLot` where dwell period overlaps alarm duration.
8. Every `Inspection` must link to an existing `Alarm`.
9. Every `Remediation` must link to an existing `Inspection`.
10. Deliberate negative test cases (such as ambiguous sensor mapping or unlinked alarms) are explicitly flagged in `ground_truth.csv` and documented in the validation report.
