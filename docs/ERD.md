# Entity-Relationship Diagram (ERD) & Schema Specification

This document details the entity relationships, keys, cardinalities, and bridge tables for the Warehouse Environmental Monitoring & Risk Traceability System.

---

## 1. Visual Entity-Relationship Diagram

```mermaid
erDiagram
    warehouses ||--o{ zones : "contains (1:N)"
    zones ||--o{ sensors : "houses (1:N)"
    zones ||--o{ door_events : "records (1:N)"
    zones ||--o{ inventory_lots : "stores (1:N)"
    zones ||--o{ alarms : "triggers (1:N)"
    
    storage_requirements ||--o{ inventory_lots : "governs (1:N)"
    sensors ||--o{ sensor_readings : "publishes (1:N)"
    
    alarms ||--o{ alarm_affected_lots : "links (1:N)"
    inventory_lots ||--o{ alarm_affected_lots : "participates (1:N)"
    
    alarms ||--o{ inspections : "triggers (1:N)"
    inspections ||--o{ remediations : "recommends (1:N)"

    warehouses {
        string warehouse_id PK
        string name
        string region
        string address
        int total_zones
        string operational_status
        timestamp created_at
    }

    zones {
        string zone_id PK
        string warehouse_id FK
        string zone_name
        string zone_type
        float target_temp_c
        float temp_min_c
        float temp_max_c
        float target_humidity_pct
        float humidity_min_pct
        float humidity_max_pct
        int max_occupancy
        int max_door_open_sec
        string status
    }

    storage_requirements {
        string requirement_id PK
        string profile_name
        string allowed_zone_types
        float temp_crit_min_c
        float temp_warn_min_c
        float temp_warn_max_c
        float temp_crit_max_c
        float humidity_crit_min_pct
        float humidity_crit_max_pct
        int max_excursion_duration_min
        string status
    }

    sensors {
        string sensor_id PK
        string zone_id FK
        string sensor_type
        string model_number
        date calibration_date
        date calibration_due
        float battery_level_pct
        float drift_offset
        string status
    }

    sensor_readings {
        string reading_id PK
        string sensor_id FK
        timestamp timestamp
        string metric_type
        float raw_value
        float calibrated_value
        string unit
        string status_code
    }

    door_events {
        string door_event_id PK
        string zone_id FK
        string door_identifier
        timestamp opened_at
        timestamp closed_at
        int duration_sec
        boolean is_ajar_violation
        string actor
    }

    inventory_lots {
        string lot_id PK
        string product_code
        string requirement_id FK
        string zone_id FK
        timestamp arrival_time
        timestamp departure_time
        float dwell_hours
        int quantity
        float unit_price_usd
        float total_value_usd
        string lifecycle_state
    }

    alarms {
        string alarm_id PK
        string zone_id FK
        string sensor_id FK
        string door_event_id FK
        string alarm_type
        string severity
        timestamp start_time
        timestamp end_time
        float duration_minutes
        float trigger_value
        float threshold_limit
        float peak_excursion
        int affected_lot_count
        float total_loss_usd
        string status
    }

    alarm_affected_lots {
        string bridge_id PK
        string alarm_id FK
        string lot_id FK
        timestamp overlap_start
        timestamp overlap_end
        float exposure_hours
        float degree_hours
        string risk_category
        string disposition_status
    }

    inspections {
        string inspection_id PK
        string alarm_id FK
        string inspector_role
        string inspector_id
        timestamp inspection_time
        string findings
        boolean physical_damage
        string recommended_action
        string status
    }

    remediations {
        string remediation_id PK
        string inspection_id FK
        string action_type
        string lot_id FK
        string sensor_id FK
        string executed_by
        string approved_by
        timestamp completed_at
        float financial_impact_usd
        string status
    }
```

---

## 2. Cardinalities and Relational Rules

1. **Warehouse to Zone (1:N)**:
   - A Warehouse contains 1 to 50 Zones. Each Zone belongs to exactly one parent Warehouse.
   - Deleting a Warehouse cascades to its Zones.
2. **Zone to Sensor (1:N)**:
   - Each Zone contains multiple environmental sensors (minimum 3: Temperature, Humidity, Occupancy).
   - Each Sensor belongs to exactly one primary Zone.
3. **Sensor to SensorReading (1:N)**:
   - Continuous time-series stream where one sensor emits thousands of observations over time.
4. **Zone to DoorEvent (1:N)**:
   - A Zone records all door open/close cycles for its physical ingress/egress doors.
5. **StorageRequirement to InventoryLot (1:N)**:
   - Standard regulatory specification applied to multiple inventory lots of matching product codes.
6. **Zone to InventoryLot (1:N)**:
   - An InventoryLot dwells in a specific storage zone for a duration between arrival and departure.
7. **Alarm to InventoryLot (N:M via `alarm_affected_lots`)**:
   - An Alarm can impact multiple lots dwelling in the zone during the alarm time window.
   - An InventoryLot can experience multiple alarms across its dwell lifetime.
   - Resolved via the `alarm_affected_lots` bridge table containing calculated spatiotemporal intersection intervals and cumulative **Degree-Hours**.
8. **Alarm to Inspection (1:N)**:
   - High and Critical alarms trigger mandatory inspection records assigned to specific roles (Plant Operator, Maintenance Engineer, Quality Engineer).
9. **Inspection to Remediation (1:N)**:
   - Corrective actions recommended by an inspection are executed and approved via dual-sign-off remediation records.
