"""Inventory Lot generation with product requirements, dwelling intervals, and values."""

import random
from datetime import datetime, timedelta
from typing import List, Dict
from wh_monitor.config import ScaleConfig, SIMULATION_START, SIMULATION_END
from wh_monitor.models import Zone, StorageRequirement, InventoryLot

PRODUCTS = [
    {"code": "MED-VAX-MRNA-90", "req": "REQ-VACCINE-ULTRA", "price": 450.0},
    {"code": "MED-BIO-INSULIN-2", "req": "REQ-PHARMA-COLD", "price": 180.0},
    {"code": "MED-BIO-ANTIBODY-5", "req": "REQ-PHARMA-COLD", "price": 820.0},
    {"code": "FOOD-DAIRY-YOGURT-1", "req": "REQ-PERISHABLE-FRESH", "price": 8.5},
    {"code": "FOOD-FRESH-BERRIES", "req": "REQ-PERISHABLE-FRESH", "price": 14.0},
    {"code": "CHEM-SOLVENT-DRY", "req": "REQ-MOISTURE-SENSITIVE", "price": 125.0},
    {"code": "DRY-TABLETS-IBUP", "req": "REQ-DRY-AMBIENT", "price": 12.0},
    {"code": "DRY-DEVICE-SENSOR", "req": "REQ-DRY-AMBIENT", "price": 95.0},
]


def generate_inventory_lots(
    zones: List[Zone],
    requirements: List[StorageRequirement],
    scale: ScaleConfig,
    rng: random.Random
) -> List[InventoryLot]:
    """Generate baseline inventory lots with temporal dwell spans and monetary valuations."""
    lots = []
    req_map = {r.requirement_id: r for r in requirements}
    
    # Map each requirement to compatible zones
    compat_zones: Dict[str, List[Zone]] = {}
    for r in requirements:
        allowed_types = set(r.allowed_zone_types.split(","))
        compat_zones[r.requirement_id] = [z for z in zones if z.zone_type in allowed_types]

    total_duration_sec = int((SIMULATION_END - SIMULATION_START).total_seconds())

    for idx in range(1, scale.num_lots + 1):
        lot_id = f"LOT-2026-{idx:06d}"
        prod = rng.choice(PRODUCTS)
        req_id = prod["req"]
        
        # Pick a compatible zone for baseline (edge case injector will deliberately misassign some later)
        eligible_zones = compat_zones.get(req_id, zones)
        assigned_zone = rng.choice(eligible_zones) if eligible_zones else rng.choice(zones)
        
        # Arrival time staggered across simulation window
        offset_start_sec = rng.randint(0, int(total_duration_sec * 0.75))
        arrival_time = SIMULATION_START + timedelta(seconds=offset_start_sec)
        
        # Dwell hours: between 6 hours and 168 hours (7 days)
        dwell_hours = round(rng.uniform(6.0, 168.0), 2)
        departure_candidate = arrival_time + timedelta(hours=dwell_hours)
        
        # Some lots are still currently dwelling in the warehouse at end of simulation window
        if departure_candidate > SIMULATION_END or rng.random() < 0.25:
            departure_time = None
            lifecycle_state = "STORED"
            # Active dwell hours calculated up to simulation end
            active_dwell = round((SIMULATION_END - arrival_time).total_seconds() / 3600.0, 2)
        else:
            departure_time = departure_candidate
            lifecycle_state = "RELEASED"
            active_dwell = dwell_hours
            
        quantity = rng.randint(25, 2500)
        unit_price = round(prod["price"] * rng.uniform(0.9, 1.15), 2)
        total_val = round(quantity * unit_price, 2)

        lots.append(
            InventoryLot(
                lot_id=lot_id,
                product_code=prod["code"],
                requirement_id=req_id,
                zone_id=assigned_zone.zone_id,
                arrival_time=arrival_time,
                departure_time=departure_time,
                dwell_hours=active_dwell,
                quantity=quantity,
                unit_price_usd=unit_price,
                total_value_usd=total_val,
                lifecycle_state=lifecycle_state
            )
        )
    return lots
