"""Deterministic PLM Seed Data Generator.

Generates a realistic mock PLM dataset (500 parts, 4-5 BOM levels, 30 suppliers,
20 documents, 15 change requests) for an industrial pump product family in SQLite
using Faker with a fixed seed.

Deliberately plants:
1. 10 near-duplicate parts (5 duplicate pairs)
2. 8 Obsolete parts still used in Released BOMs
3. 12 Buy parts with no supplier (AML gaps)
4. 5 EBOM vs MBOM mismatches
5. 6 parts with non-compliant RoHS materials
"""

import argparse
import json
import random
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from faker import Faker

# Fixed random seed for complete determinism
RANDOM_SEED = 42


def get_deterministic_uuid(namespace: str, index: int) -> str:
    """Generate reproducible UUID from namespace and index."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{namespace}-{index}"))


def create_schema(conn: sqlite3.Connection) -> None:
    """Read and execute schema.sql on the target connection."""
    schema_path = Path(__file__).parent / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        ddl = f.read()
    conn.executescript(ddl)
    conn.commit()


def generate_dataset(db_path: str = "plm_mock.db") -> dict[str, Any]:
    """Generate the full deterministic mock PLM dataset."""
    random.seed(RANDOM_SEED)
    Faker.seed(RANDOM_SEED)
    fake = Faker()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF;")  # Disable temporarily during bulk load

    create_schema(conn)
    cursor = conn.cursor()

    # Clear any existing tables
    tables = [
        "iiot_sensor_events", "iiot_devices",
        "qms_defect_reports",
        "erp_purchase_orders", "erp_inventory",
        "aml_links", "manufacturer_parts", "manufacturers",
        "change_resulting_items", "change_affected_items", "change_notices", "change_requests",
        "part_doc_links", "document_versions", "document_masters",
        "bom_links", "part_versions", "part_masters"
    ]
    for tbl in tables:
        cursor.execute(f"DELETE FROM {tbl}")
    conn.commit()

    base_time = datetime(2025, 1, 15, 8, 30, 0)

    # =========================================================================
    # 1. GENERATE 30 SUPPLIERS
    # =========================================================================
    supplier_names = [
        ("SKF Bearing Group", "9SKF1", "Sweden"),
        ("Flowserve Fluid Motion", "1FSV2", "USA"),
        ("EagleBurgmann Seals", "4EB03", "Germany"),
        ("Timken Industrial Bearings", "2TMK4", "USA"),
        ("Parker Hannifin Seal Group", "3PH05", "USA"),
        ("Swagelok Fluid Systems", "8SWG6", "USA"),
        ("Fastenal Aerospace & Industrial", "1FST7", "USA"),
        ("Garlock Sealing Technologies", "5GAR8", "USA"),
        ("Siemens Industrial Motors", "0SIE9", "Germany"),
        ("WEG Electric Corporation", "6WEG0", "Brazil"),
        ("Sandvik Materials Technology", "7SND1", "Sweden"),
        ("Carpenter Technology Alloys", "2CRP2", "USA"),
        ("Flexitallic Gasket Company", "3FLX3", "UK"),
        ("John Crane Mechanical Seals", "4JCR4", "USA"),
        ("NSK Precision Bearings", "9NSK5", "Japan"),
        ("NTN Bearing Corporation", "8NTN6", "Japan"),
        ("Freudenberg Sealing Technologies", "7FRD7", "Germany"),
        ("Trelleborg Sealing Solutions", "6TRL8", "Sweden"),
        ("Haynes International High-Temp Alloys", "5HYN9", "USA"),
        ("McMaster-Carr Supply Co.", "1MMC0", "USA"),
        ("ABB Motion & Drives", "0ABB1", "Switzerland"),
        ("KSB Fluid Systems", "9KSB2", "Germany"),
        ("Sulzer Pumps Equipment", "8SLZ3", "Switzerland"),
        ("Waukesha Bearings Corp", "7WKB4", "USA"),
        ("Greene Tweed High Performance Seals", "6GNT5", "USA"),
        ("Bal Seal Engineering", "5BAL6", "USA"),
        ("Anker-Holth Fluid Power", "4ANK7", "Canada"),
        ("Victaulic Piping Solutions", "3VIC8", "USA"),
        ("Spirax Sarco Steam & Fluid", "2SPX9", "UK"),
        ("Schunk Carbon Technology", "1SCK0", "Germany"),
    ]

    suppliers: list[dict[str, Any]] = []
    for idx, (s_name, cage, country) in enumerate(supplier_names):
        m_id = get_deterministic_uuid("supplier", idx)
        created_at = (base_time + timedelta(days=idx)).isoformat()
        cursor.execute(
            """
            INSERT INTO manufacturers (id, name, cage_code, status, country, created_at)
            VALUES (?, ?, ?, 'ACTIVE', ?, ?)
            """,
            (m_id, s_name, cage, country, created_at),
        )
        suppliers.append({"id": m_id, "name": s_name, "cage": cage, "country": country})

    # Create catalog parts for suppliers
    mfr_parts: list[dict[str, Any]] = []
    for s_idx, sup in enumerate(suppliers):
        for p_idx in range(1, 6):
            mp_id = get_deterministic_uuid(f"mfr_part_{s_idx}", p_idx)
            catalog_no = f"{sup['name'][:3].upper()}-{1000 + s_idx * 10 + p_idx}"
            desc = f"Commercial item {catalog_no} certified by {sup['name']}"
            cursor.execute(
                """
                INSERT INTO manufacturer_parts (id, manufacturer_id, mfr_part_number, description, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (mp_id, sup["id"], catalog_no, desc, base_time.isoformat()),
            )
            mfr_parts.append({
                "id": mp_id,
                "supplier_id": sup["id"],
                "supplier_name": sup["name"],
                "mfr_part_number": catalog_no,
            })
    conn.commit()

    # =========================================================================
    # 2. DEFINE PLANTED ISSUES DEFINITIONS
    # =========================================================================

    # 1. 10 Near-Duplicate Parts (5 Pairs)
    duplicate_pairs = [
        # Pair 1: Hex Cap Screw M12x45mm 316SS
        (41, 42,
         "Hex Head Cap Screw M12x1.75 x 45mm SS316",
         "Screw, Hex Flange M12-1.75 x 45mm - 316SS",
         "316L Stainless Steel", "BUY"),
        # Pair 2: Viton O-Ring 75mm x 3.5mm
        (88, 89,
         "O-Ring 75.0mm ID x 3.5mm CS Viton A 75",
         "Fluoroelastomer O-Ring Seal 75x3.5mm FKM",
         "Viton FKM 75A", "BUY"),
        # Pair 3: Deep Groove Ball Bearing 6309 C3
        (145, 146,
         "Deep Groove Ball Bearing 6309-2Z/C3 (45x100x25)",
         "Single Row Radial Bearing 6309 ZZ C3 45mm Bore",
         "52100 Chrome Steel", "BUY"),
        # Pair 4: Shaft Sleeve 50mm x 65mm x 80mm Duplex
        (210, 211,
         "Dynamic Shaft Sleeve 50mm ID x 65mm OD x 80mm L",
         "Shaft Protection Sleeve OD65 ID50 L80 Duplex",
         "Duplex 2205", "MAKE"),
        # Pair 5: PTFE Spiral Wound Gasket 4 Inch Class 300
        (335, 336,
         "Spiral Wound Gasket 4 Inch 300# 316L/PTFE Inner Ring",
         "4 Inch Class 300 ASME B16.20 SWG Gasket 316/PTFE",
         "316L/PTFE", "BUY"),
    ]
    duplicate_part_nums = set()
    for p1, p2, _, _, _, _ in duplicate_pairs:
        duplicate_part_nums.add(p1)
        duplicate_part_nums.add(p2)

    # 2. 8 Obsolete parts still used in Released BOMs
    obsolete_part_indices = {55, 92, 130, 175, 220, 280, 315, 390}

    # 3. 12 Buy parts with NO supplier (AML missing)
    no_supplier_buy_indices = {61, 74, 112, 158, 199, 245, 268, 305, 348, 382, 422, 465}

    # 5. 6 parts with RoHS Non-Compliant Materials
    rohs_non_compliant_map = {
        18: ("Free-Cutting Brass Drain Plug 1/4 Inch NPT",
             "Free-Machining Brass UNS C36000 (Lead Pb > 4.2% wt)"),
        82: ("High-Tensile Casing Tie-Rod M24x300",
             "Cadmium Plated AISI 4140 Alloy Steel"),
        164: ("Zinc-Plated Baseplate Levelling Shims",
              "Carbon Steel with Yellow Hexavalent Chromium (Cr VI) Passivation"),
        238: ("Bearing Sump Thermal Tilt Switch Sensor",
              "Mercury Wetted Glass Contact Switch (Hg > 0.5g)"),
        322: ("Gland Packing Seal Ring 5/8 Inch Sq",
              "PTFE Impregnated Yarn with Decabromodiphenyl Ether (Deca-BDE Flame Retardant)"),
        415: ("Submersible Casing Power Cable Sheath 3m",
              "Flexible PVC containing Di(2-ethylhexyl) phthalate (DEHP > 2.5% wt)"),
    }

    # Standard Compliant Engineering Materials
    compliant_materials = [
        "Cast Iron ASTM A48 Class 30",
        "Ductile Iron ASTM A536",
        "Cast Steel ASTM A216 WCB",
        "316L Stainless Steel",
        "Duplex 2205 Stainless Steel",
        "Super Duplex 2507",
        "Hastelloy C-276",
        "Titanium Grade 2",
        "Aluminum Bronze C95400",
        "Silicon Carbide (SiC)",
        "Tungsten Carbide (WC)",
        "Carbon Steel AISI 1045",
        "Alloy Steel 4140 Quenched & Tempered",
        "17-4 PH Stainless Steel (H1150)",
        "Viton FKM Fluoroelastomer",
        "PTFE Virgin Grade",
        "EPDM Commercial Grade",
        "Expanded Flexible Graphite",
    ]

    # =========================================================================
    # 3. GENERATE 500 PARTS (PMP-0001 to PMP-0500)
    # =========================================================================
    parts: list[dict[str, Any]] = []

    # Level 0 Top Assemblies (PMP-0001 to PMP-0005)
    top_assemblies = [
        (1, "PMP-0001", "ApexFlow 1000 End-Suction Centrifugal Pump", "API 610 Overhung general process pump", "B", 1, "RELEASED", "MAKE", "Cast Steel ASTM A216 WCB"),
        (2, "PMP-0002", "TitanSlurry 2000 Heavy-Duty Mineral Slurry Pump", "Severe-duty abrasion resistant slurry pump", "A", 2, "RELEASED", "MAKE", "High Chrome White Iron 28% Cr"),
        (3, "PMP-0003", "ChemGuard 3000 Petrochemical Process Pump", "API 610 BB2 between-bearings chemical pump", "A", 1, "RELEASED", "MAKE", "Duplex 2205 Stainless Steel"),
        (4, "PMP-0004", "HydroPress 4000 High-Pressure Multistage Boiler Pump", "Ring-section high pressure feedwater pump", "B", 2, "RELEASED", "MAKE", "Forged Carbon Steel A105"),
        (5, "PMP-0005", "MagDrive 5000 Sealless Magnetic Drive Chemical Pump", "Zero-leakage magnetic containment pump", "A", 1, "RELEASED", "MAKE", "Hastelloy C-276"),
    ]

    # Component title pools for realistic procedural generation
    pump_noun_pool = [
        "Volute Casing", "Impeller", "Shaft", "Power Frame", "Bearing Housing",
        "Stuffing Box", "Mechanical Seal Cartridge", "Shaft Sleeve", "Throttle Bushing",
        "Wear Ring", "Suction Head", "Discharge Nozzle", "Lantern Ring", "Gland Follower",
        "Deflector Slinger", "Bearing Isolator", "Locknut & Lockwasher", "Oil Sight Glass",
        "Breather Vent", "Coupling Hub", "Coupling Spacer", "Baseplate Frame",
        "Anchor Bracket", "Flange Adapter", "O-Ring Seal", "Spiral Wound Gasket",
        "Radial Ball Bearing", "Angular Contact Thrust Bearing", "Cylindrical Roller Bearing",
        "Hex Head Cap Screw", "Stud Bolt", "Hex Heavy Nut", "Dowel Alignment Pin",
        "Keyway Drive Key", "Internal Retaining Ring", "Wave Spring", "Thermal RTD Sensor",
        "Vibration Sensor Probe", "Drain Valve", "Gauge Orifice Ring", "Seal Flush Pipe"
    ]

    for num in range(1, 501):
        part_no = f"PMP-{num:04d}"
        created_at = (base_time + timedelta(hours=num * 2)).isoformat()
        updated_at = (base_time + timedelta(hours=num * 2 + 10)).isoformat()

        if num <= 5:
            # Top-level pumps
            _, _, p_name, p_desc, rev, it, state, mb, mat = top_assemblies[num - 1]
        elif num in duplicate_part_nums:
            # Planted Near-Duplicates
            for p1, p2, n1, n2, mat_dup, mb_dup in duplicate_pairs:
                if num == p1:
                    p_name = n1
                    p_desc = f"Precision mechanical component - Spec: {mat_dup}"
                    rev, it, state, mb, mat = "A", 1, "RELEASED", mb_dup, mat_dup
                    break
                elif num == p2:
                    p_name = n2
                    p_desc = f"Precision mechanical component - Spec: {mat_dup}"
                    rev, it, state, mb, mat = "A", 1, "RELEASED", mb_dup, mat_dup
                    break
        elif num in rohs_non_compliant_map:
            # Planted RoHS non-compliant parts
            p_name, mat = rohs_non_compliant_map[num]
            p_desc = f"Legacy design standard component using {mat}"
            rev, it, state, mb = "A", 1, "RELEASED", "BUY" if num % 2 == 0 else "MAKE"
        elif num in obsolete_part_indices:
            # Planted Obsolete parts
            p_name = f"Legacy {random.choice(pump_noun_pool)} Series-Old"
            p_desc = "Obsolete component superseded by newer engineering revision"
            rev, it, state, mb = "A", 3, "OBSOLETE", "BUY" if num % 2 == 0 else "MAKE"
            mat = random.choice(compliant_materials)
        elif num in no_supplier_buy_indices:
            # Planted BUY parts with no supplier
            p_name = f"Commercial {random.choice(pump_noun_pool)} Component"
            p_desc = "Outsourced catalog item pending AML qualification"
            rev, it, state, mb = "A", 1, "RELEASED", "BUY"
            mat = random.choice(compliant_materials)
        elif num <= 35 or num in (36, 40):
            # Level 1 and selected Level 2 parent subassemblies are in active production (RELEASED)
            noun = random.choice(pump_noun_pool)
            spec_size = f"{random.choice([25, 40, 50, 65, 80, 100, 150, 200, 250, 300])}mm"
            p_name = f"{noun} Subassembly {spec_size}"
            p_desc = f"Major pump subassembly module: {noun} ({spec_size})"
            rev = "A"
            it = 1
            state = "RELEASED"
            mb = "MAKE"
            mat = random.choice(compliant_materials)
        else:
            # Normal distribution for remaining components (only RELEASED, IN_WORK, UNDER_REVIEW)
            noun = random.choice(pump_noun_pool)
            spec_size = f"{random.choice([25, 40, 50, 65, 80, 100, 150, 200, 250, 300])}mm"
            p_name = f"{noun} {spec_size}"
            p_desc = f"Industrial pump standard component: {noun} ({spec_size})"

            # Revision and states: deliberately omit OBSOLETE so only planted 8 are obsolete
            state_roll = random.random()
            if state_roll < 0.75:
                state = "RELEASED"
                rev = random.choice(["A", "B", "C"])
                it = random.choice([1, 2])
            elif state_roll < 0.90:
                state = "IN_WORK"
                rev = "B" if random.random() > 0.5 else "A"
                it = random.choice([1, 2, 3])
            else:
                state = "UNDER_REVIEW"
                rev = "A"
                it = 1

            # Make vs Buy
            mb = "BUY" if num > 180 and random.random() > 0.35 else "MAKE"
            mat = random.choice(compliant_materials)

        m_id = get_deterministic_uuid("part_master", num)
        v_id = get_deterministic_uuid("part_version", num)

        cursor.execute(
            """
            INSERT INTO part_masters (id, part_number, name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (m_id, part_no, p_name, created_at),
        )

        cursor.execute(
            """
            INSERT INTO part_versions (
                id, master_id, revision, iteration, lifecycle_state,
                description, make_buy, material, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'wcadmin', ?, ?)
            """,
            (v_id, m_id, rev, it, state, p_desc, mb, mat, created_at, updated_at),
        )

        parts.append({
            "num": num,
            "master_id": m_id,
            "version_id": v_id,
            "part_number": part_no,
            "name": p_name,
            "revision": rev,
            "iteration": it,
            "version_label": f"{rev}.{it}",
            "lifecycle_state": state,
            "make_buy": mb,
            "material": mat,
        })
    conn.commit()

    # Part number lookup map
    part_by_num = {p["num"]: p for p in parts}

    # =========================================================================
    # 4. ASSOCIATE SUPPLIERS & AML LINKS (EXCEPT THE 12 UNASSIGNED BUY PARTS)
    # =========================================================================
    aml_count = 0
    for p in parts:
        if p["make_buy"] == "BUY" and p["num"] not in no_supplier_buy_indices:
            # Link to 1 or 2 suppliers
            sup_selection = random.sample(mfr_parts, k=random.choice([1, 2]))
            for rank, s_part in enumerate(sup_selection, start=1):
                aml_id = get_deterministic_uuid("aml", aml_count)
                status = "PREFERRED" if rank == 1 else "APPROVED"
                cursor.execute(
                    """
                    INSERT INTO aml_links (
                        id, part_master_id, mfr_part_id, sourcing_status, preference_rank
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (aml_id, p["master_id"], s_part["id"], status, rank),
                )
                aml_count += 1
    conn.commit()

    # =========================================================================
    # 5. BUILD HIERARCHICAL BOM STRUCTURE (4 TO 5 LEVELS DEEP)
    # =========================================================================
    # Hierarchy layout:
    # Level 0: Pumps PMP-0001 .. PMP-0005
    # Level 1 Subassemblies: PMP-0006 .. PMP-0035 (each Top Pump gets 6 major subassemblies)
    # Level 2 Subassemblies: PMP-0036 .. PMP-0110 (each Level 1 gets 2-3 Level 2 subassemblies)
    # Level 3 Component Groups: PMP-0111 .. PMP-0220 (each Level 2 gets 2-3 Level 3 subassemblies)
    # Level 4 Component Parts: PMP-0221 .. PMP-0380
    # Level 5 Hardware & Fasteners: PMP-0381 .. PMP-0500

    bom_links: list[dict[str, Any]] = []
    bom_link_id_counter = 0

    def add_link(parent_idx: int, child_idx: int, qty: float, unit: str = "ea",
                 find_no: int | None = None, ref_des: str | None = None,
                 bom_type: str = "EBOM", notes: str = ""):
        nonlocal bom_link_id_counter
        parent_p = part_by_num[parent_idx]
        child_p = part_by_num[child_idx]
        link_id = get_deterministic_uuid("bom_link", bom_link_id_counter)
        bom_link_id_counter += 1

        cursor.execute(
            """
            INSERT INTO bom_links (
                id, parent_version_id, child_master_id, quantity, unit,
                find_number, ref_designators, bom_type, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                link_id, parent_p["version_id"], child_p["master_id"],
                qty, unit, find_no, ref_des, bom_type, notes
            ),
        )
        bom_links.append({
            "id": link_id,
            "parent_part_number": parent_p["part_number"],
            "child_part_number": child_p["part_number"],
            "quantity": qty,
            "unit": unit,
            "find_number": find_no,
            "bom_type": bom_type,
            "notes": notes,
        })

    # A. Level 0 -> Level 1 (Major Subassemblies)
    # PMP-0001 (Pump 1) gets Level 1 subassemblies 6 to 11
    # PMP-0002 (Pump 2) gets Level 1 subassemblies 12 to 17
    # PMP-0003 (Pump 3) gets Level 1 subassemblies 18 to 23
    # PMP-0004 (Pump 4) gets Level 1 subassemblies 24 to 29
    # PMP-0005 (Pump 5) gets Level 1 subassemblies 30 to 35
    for top_idx in range(1, 6):
        start_sub = 6 + (top_idx - 1) * 6
        for offset in range(6):
            child_sub = start_sub + offset
            add_link(top_idx, child_sub, qty=1.0, find_no=(offset + 1) * 10, bom_type="EBOM")
            add_link(top_idx, child_sub, qty=1.0, find_no=(offset + 1) * 10, bom_type="MBOM")

    # B. Level 1 -> Level 2 Subassemblies (6..35 -> 36..110)
    # Exclude planted obsolete parts so they are only linked via explicit obsolete_usages
    l2_start = 36
    l2_end = 110
    l2_list = [x for x in range(l2_start, l2_end + 1) if x not in obsolete_part_indices]
    for i, l2_idx in enumerate(l2_list):
        parent_l1 = 6 + (i % 30)  # assign to one of the 30 Level 1 subassemblies
        add_link(parent_l1, l2_idx, qty=1.0, find_no=(i % 5 + 1) * 10, bom_type="EBOM")
        add_link(parent_l1, l2_idx, qty=1.0, find_no=(i % 5 + 1) * 10, bom_type="MBOM")

    # C. Level 2 -> Level 3 Component Groups (36..110 -> 111..220)
    l3_start = 111
    l3_end = 220
    l3_list = [x for x in range(l3_start, l3_end + 1) if x not in obsolete_part_indices]
    for i, l3_idx in enumerate(l3_list):
        parent_l2 = 36 + (i % 75)
        qty = random.choice([1.0, 2.0])
        add_link(parent_l2, l3_idx, qty=qty, find_no=(i % 6 + 1) * 10, bom_type="EBOM")
        add_link(parent_l2, l3_idx, qty=qty, find_no=(i % 6 + 1) * 10, bom_type="MBOM")

    # D. Level 3 -> Level 4 Piece Parts (111..220 -> 221..380)
    l4_start = 221
    l4_end = 380
    l4_list = [x for x in range(l4_start, l4_end + 1) if x not in obsolete_part_indices]
    for i, l4_idx in enumerate(l4_list):
        parent_l3 = 111 + (i % 110)
        qty = random.choice([1.0, 2.0, 4.0, 8.0])
        add_link(parent_l3, l4_idx, qty=qty, find_no=(i % 8 + 1) * 10, bom_type="EBOM")
        add_link(parent_l3, l4_idx, qty=qty, find_no=(i % 8 + 1) * 10, bom_type="MBOM")

    # E. Level 4 -> Level 5 Hardware & Fasteners (221..380 -> 381..500)
    l5_start = 381
    l5_end = 500
    l5_list = [x for x in range(l5_start, l5_end + 1) if x not in obsolete_part_indices]
    for i, l5_idx in enumerate(l5_list):
        parent_l4 = 221 + (i % 160)
        qty = random.choice([2.0, 4.0, 6.0, 12.0, 16.0])
        add_link(parent_l4, l5_idx, qty=qty, find_no=(i % 10 + 1) * 10, bom_type="EBOM")
        add_link(parent_l4, l5_idx, qty=qty, find_no=(i % 10 + 1) * 10, bom_type="MBOM")

    # =========================================================================
    # PLANT ISSUE 2: 8 Obsolete Parts used in Released Parent Assemblies
    # =========================================================================
    # Connect the 8 obsolete parts into Released parent assemblies
    obsolete_usages = [
        (6, 55, 1.0, "Throttle Bushing"),      # PMP-0006 (Released) -> PMP-0055 (Obsolete)
        (9, 92, 1.0, "Mechanical Seal"),       # PMP-0009 (Released) -> PMP-0092 (Obsolete)
        (7, 130, 1.0, "Impeller Lock Nut"),    # PMP-0007 (Released) -> PMP-0130 (Obsolete)
        (36, 175, 2.0, "Lip Seal"),            # PMP-0036 (Released) -> PMP-0175 (Obsolete)
        (12, 220, 1.0, "Asbestos Gasket"),     # PMP-0012 (Released) -> PMP-0220 (Obsolete)
        (40, 280, 1.0, "Lantern Ring"),        # PMP-0040 (Released) -> PMP-0280 (Obsolete)
        (13, 315, 1.0, "Impeller Vane Shroud"),# PMP-0013 (Released) -> PMP-0315 (Obsolete)
        (1, 390, 2.0, "Lifting Lug Eyebolt"),  # PMP-0001 (Released) -> PMP-0390 (Obsolete)
    ]
    for p_parent, p_child, q, note in obsolete_usages:
        add_link(p_parent, p_child, qty=q, find_no=95, bom_type="EBOM", notes=f"PLANTED_OBSOLETE: {note}")
        add_link(p_parent, p_child, qty=q, find_no=95, bom_type="MBOM", notes=f"PLANTED_OBSOLETE: {note}")

    # =========================================================================
    # PLANT ISSUE 4: 5 EBOM vs MBOM Mismatches
    # =========================================================================
    # Mismatch 1: Quantity mismatch (EBOM=16, MBOM=20)
    add_link(1, 25, qty=16.0, find_no=80, bom_type="EBOM", notes="PLANTED_MISMATCH: Casing Studs Qty 16")
    add_link(1, 25, qty=20.0, find_no=80, bom_type="MBOM", notes="PLANTED_MISMATCH: Casing Studs Qty 20 (Includes 4 shop clamping studs)")

    # Mismatch 2: Part present only in MBOM (balancing weights added during shop balancing)
    add_link(7, 78, qty=2.0, find_no=85, bom_type="MBOM", notes="PLANTED_MISMATCH: Balance Weights added in MBOM only")

    # Mismatch 3: Assembly tool spacer present only in MBOM
    add_link(9, 105, qty=1.0, find_no=90, bom_type="MBOM", notes="PLANTED_MISMATCH: Seal Alignment Spacer in MBOM only")

    # Mismatch 4: Shims quantity variance (EBOM=2, MBOM=5)
    add_link(8, 140, qty=2.0, find_no=75, bom_type="EBOM", notes="PLANTED_MISMATCH: Bearing Shims Qty 2")
    add_link(8, 140, qty=5.0, find_no=75, bom_type="MBOM", notes="PLANTED_MISMATCH: Bearing Shims Qty 5 (Tolerance stackup pack)")

    # Mismatch 5: Part present in EBOM but dropped from MBOM (ship-loose kit discrepancy)
    add_link(10, 290, qty=1.0, find_no=70, bom_type="EBOM", notes="PLANTED_MISMATCH: Coupling Guard in EBOM (missing in MBOM)")

    conn.commit()

    # =========================================================================
    # 6. GENERATE 20 DOCUMENTS
    # =========================================================================
    doc_types = ["SPECIFICATION", "CAD_DRAWING", "TEST_REPORT", "USER_MANUAL"]
    doc_titles = [
        ("DOC-SPEC-1001", "ApexFlow 1000 API 610 Engineering Specification", "SPECIFICATION", "ApexFlow1000_Spec.pdf", 1),
        ("DOC-CAD-1001", "ApexFlow 1000 3D Master CAD Assembly Model", "CAD_DRAWING", "ApexFlow1000_TopAssembly.asm", 1),
        ("DOC-TR-1001", "ApexFlow 1000 Hydrostatic Pressure Test Certificate", "TEST_REPORT", "HydroTest_ApexFlow1001.pdf", 1),
        ("DOC-MAN-1001", "ApexFlow 1000 Installation & Maintenance Operations Manual", "USER_MANUAL", "ApexFlow_O&M_Manual.pdf", 1),
        ("DOC-SPEC-2001", "TitanSlurry 2000 Severe Duty Slurry Pump Technical Spec", "SPECIFICATION", "TitanSlurry_Spec.pdf", 2),
        ("DOC-CAD-2001", "TitanSlurry 2000 Casing & Liner CAD Model", "CAD_DRAWING", "TitanSlurry_Casing.prt", 2),
        ("DOC-TR-2001", "TitanSlurry 2000 Slurry Impeller Dynamic Balancing Report", "TEST_REPORT", "BalanceCert_Titan2001.pdf", 2),
        ("DOC-SPEC-3001", "ChemGuard 3000 Petrochemical Process Pump Datasheet", "SPECIFICATION", "ChemGuard3000_Datasheet.pdf", 3),
        ("DOC-CAD-3001", "ChemGuard 3000 Dual Cartridge Mechanical Seal 3D CAD", "CAD_DRAWING", "ChemGuard_DualSeal.asm", 9),
        ("DOC-TR-3001", "ChemGuard 3000 API 682 Seal Flush Plan 11/53A Hydro Report", "TEST_REPORT", "Plan53A_TestReport.pdf", 9),
        ("DOC-SPEC-4001", "HydroPress 4000 Multistage Boiler Feed Pump Specification", "SPECIFICATION", "HydroPress_Spec.pdf", 4),
        ("DOC-CAD-4001", "HydroPress 4000 Intermediate Stage Diffuser CAD Model", "CAD_DRAWING", "HydroPress_Diffuser.prt", 4),
        ("DOC-TR-4001", "HydroPress 4000 High Pressure Hydraulic Performance Test Curve", "TEST_REPORT", "PumpCurve_HydroPress4000.pdf", 4),
        ("DOC-SPEC-5001", "MagDrive 5000 Sealless Containment Shell Design Criteria", "SPECIFICATION", "MagDrive_Containment_Spec.pdf", 5),
        ("DOC-CAD-5001", "MagDrive 5000 Magnetic Coupling & Rotor Assembly CAD", "CAD_DRAWING", "MagDrive_Coupling.asm", 5),
        ("DOC-TR-5001", "MagDrive 5000 Eddy Current Loss & Thermal Dissipation Test", "TEST_REPORT", "ThermalTest_MagDrive.pdf", 5),
        ("DOC-CAD-0010", "Structural Channel Skid Baseplate Fabrication Drawing", "CAD_DRAWING", "Baseplate_Skid_Weldment.drw", 11),
        ("DOC-SPEC-0020", "Welding Procedure Specification (WPS) for Duplex 2205", "SPECIFICATION", "WPS_Duplex_2205.pdf", 3),
        ("DOC-TR-0030", "Material Test Report (MTR) 3.1 Mill Certificate for Castings", "TEST_REPORT", "MTR_Casing_Heat4091.pdf", 6),
        ("DOC-MAN-0040", "Cartridge Mechanical Seal Field Replacement Guide", "USER_MANUAL", "CartridgeSeal_FieldGuide.pdf", 9),
    ]

    for d_idx, (d_no, d_title, d_type, fname, linked_p_idx) in enumerate(doc_titles):
        m_id = get_deterministic_uuid("doc_master", d_idx)
        v_id = get_deterministic_uuid("doc_version", d_idx)
        created_at = (base_time + timedelta(days=d_idx)).isoformat()

        cursor.execute(
            """
            INSERT INTO document_masters (id, doc_number, name, doc_type, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (m_id, d_no, d_title, d_type, created_at),
        )

        cursor.execute(
            """
            INSERT INTO document_versions (
                id, master_id, revision, iteration, lifecycle_state,
                file_name, file_size_bytes, mime_type, file_uri,
                created_by, created_at, updated_at
            ) VALUES (?, ?, 'A', 1, 'RELEASED', ?, ?, ?, ?, 'wcadmin', ?, ?)
            """,
            (
                v_id, m_id, fname, random.randint(500000, 15000000),
                "application/pdf" if fname.endswith(".pdf") else "application/octet-stream",
                f"vault://docs/{d_no}/{fname}",
                created_at, created_at
            ),
        )

        # Link document to part
        target_p = part_by_num[linked_p_idx]
        link_id = get_deterministic_uuid("doc_part_link", d_idx)
        link_type = "DESCRIBES" if d_type in ("SPECIFICATION", "CAD_DRAWING") else "REFERENCES"
        cursor.execute(
            """
            INSERT INTO part_doc_links (id, part_version_id, doc_version_id, link_type)
            VALUES (?, ?, ?, ?)
            """,
            (link_id, target_p["version_id"], v_id, link_type),
        )
    conn.commit()

    # =========================================================================
    # 7. GENERATE 15 CHANGE REQUESTS IN DIFFERENT STATES
    # =========================================================================
    cr_data = [
        ("CR-0001", "Replace Obsolete Throttle Bushing with Carbon Composite",
         "PMP-0055 is obsolete and causes supply chain blockages during casing assembly.",
         "DEFECT", "HIGH", "OPEN", [55, 6]),
        ("CR-0002", "Investigate RoHS Non-Compliance on C36000 Brass Drain Plug",
         "PMP-0018 exceeds maximum permissible lead limit (4.2% Pb vs 4.0% exemption).",
         "COMPLIANCE", "EMERGENCY", "UNDER_REVIEW", [18]),
        ("CR-0003", "Qualify Alternate Sourcing for PMP-0061 Silicon Carbide Ring",
         "Component currently has zero registered suppliers in AML causing single-source risk.",
         "COST_REDUCTION", "MEDIUM", "APPROVED", [61]),
        ("CR-0004", "Resolve EBOM vs MBOM Stud Quantity Variance on ApexFlow Casing",
         "EBOM specifies 16 studs but shop floor MBOM consumes 20 studs due to clamp tooling.",
         "DEFECT", "HIGH", "RESOLVED", [1, 25]),
        ("CR-0005", "Eliminate Duplicate Fastener Part Numbers PMP-0041 and PMP-0042",
         "Inventory consolidation: merge M12x45mm 316SS hex cap screws under a single master.",
         "COST_REDUCTION", "LOW", "UNDER_REVIEW", [41, 42]),
        ("CR-0006", "Urgent Elimination of Cadmium Plating on Tie-Rod PMP-0082",
         "EU REACH Annex XVII ban on cadmium-plated structural fasteners requires immediate redesign.",
         "COMPLIANCE", "EMERGENCY", "APPROVED", [82]),
        ("CR-0007", "Obsolete Asbestos Gasket PMP-0220 Replacement with Flexible Graphite",
         "Plant audit detected legacy compressed asbestos gasket still referenced in released BOM.",
         "COMPLIANCE", "HIGH", "OPEN", [220, 12]),
        ("CR-0008", "Upgrade Slurry Impeller Metallurgy to 28% Chrome White Iron",
         "Field cavitation wear on standard duplex impellers indicates need for high-chrome alloy.",
         "DESIGN_IMPROVEMENT", "MEDIUM", "APPROVED", [2, 7]),
        ("CR-0009", "Consolidate Viton O-Ring Part Duplicates PMP-0088 and PMP-0089",
         "Both part numbers have identical 75x3.5mm geometry from Parker and Freudenberg.",
         "COST_REDUCTION", "LOW", "REJECTED", [88, 89]),
        ("CR-0010", "De-energize Mercury Tilt Switch PMP-0238 with Solid-State Accelerometer",
         "Mercury-wetted mechanical switch violates RoHS Directive 2011/65/EU.",
         "COMPLIANCE", "HIGH", "UNDER_REVIEW", [238]),
        ("CR-0011", "Clarify MBOM Impeller Balance Weight Addition on PMP-1200",
         "Shop adds 2x PMP-0078 balance weights which are absent in engineering master BOM.",
         "DESIGN_IMPROVEMENT", "MEDIUM", "OPEN", [7, 78]),
        ("CR-0012", "Implement Inconel Wave Spring Sourcing for Mechanical Seal Cartridge",
         "PMP-0074 currently lacks qualified suppliers in active approved vendor list.",
         "COST_REDUCTION", "MEDIUM", "RESOLVED", [74, 9]),
        ("CR-0013", "Resolve Coupling Guard Omission between EBOM and MBOM",
         "Coupling guard PMP-0290 present in engineering BOM was omitted from manufacturing bill.",
         "DEFECT", "HIGH", "APPROVED", [10, 290]),
        ("CR-0014", "Standardize Deep Groove Ball Bearing 6309 C3 Part Numbers",
         "PMP-0145 and PMP-0146 represent duplicate inventory entries for standard 6309 bearing.",
         "COST_REDUCTION", "LOW", "REJECTED", [145, 146]),
        ("CR-0015", "Phase-out Deca-BDE Flame Retardant Gland Packing PMP-0322",
         "Replace halogenated packing yarn with clean virgin PTFE graphite braided packing.",
         "COMPLIANCE", "HIGH", "RESOLVED", [322]),
    ]

    for c_idx, (cr_no, title, desc, cat, prio, state, affected_indices) in enumerate(cr_data):
        cr_id = get_deterministic_uuid("change_request", c_idx)
        created_at = (base_time + timedelta(days=c_idx * 2)).isoformat()
        affected_part_numbers = [part_by_num[p_idx]["part_number"] for p_idx in affected_indices]

        cursor.execute(
            """
            INSERT INTO change_requests (
                id, cr_number, title, description, category, priority,
                state, affected_parts, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cr_id, cr_no, title, desc, cat, prio, state,
                json.dumps(affected_part_numbers), created_at, created_at
            ),
        )

        # For approved / resolved change requests, create a corresponding Change Notice (ECN)
        if state in ("APPROVED", "RESOLVED"):
            cn_id = get_deterministic_uuid("change_notice", c_idx)
            cn_no = f"CN-{c_idx + 1:04d}"
            cn_state = "COMPLETED" if state == "RESOLVED" else "IN_WORK"
            cursor.execute(
                """
                INSERT INTO change_notices (
                    id, cn_number, change_request_id, title, description,
                    state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cn_id, cn_no, cr_id, f"ECN Execution: {title}",
                    f"Implementation directive for {cr_no}", cn_state,
                    created_at, created_at
                ),
            )
            for p_num in affected_part_numbers:
                aff_id = get_deterministic_uuid(f"cn_aff_{c_idx}", p_num)
                cursor.execute(
                    """
                    INSERT INTO change_affected_items (
                        id, change_notice_id, item_type, item_number,
                        version_label, disposition
                    ) VALUES (?, ?, 'PART', ?, 'A.1', 'REWORK')
                    """,
                    (aff_id, cn_id, p_num),
                )

    # =========================================================================
    # 7. GENERATE ERP INVENTORY & PURCHASE ORDERS
    # =========================================================================
    warehouses = [
        ("WH-CENTRAL-01", "ApexFlow Central Distribution", "Chicago, IL"),
        ("WH-PLANT-02", "Houston Manufacturing Plant", "Houston, TX"),
        ("WH-SERVICE-03", "Rotterdam Service Hub", "Rotterdam, NL"),
    ]

    erp_inventory_count = 0
    # Seed inventory for all parts
    for idx, p in enumerate(parts):
        p_no = p["part_number"]
        base_cost = 15.0 + (idx % 45) * 5.5

        if p_no == "PMP-0290":  # Failing part
            inv_pmp290 = [
                ("WH-CENTRAL-01", "ApexFlow Central Distribution", "A-14-02", 180.0, 35.0, 145.0, 40.0, 142.50),
                ("WH-PLANT-02", "Houston Manufacturing Plant", "B-03-11", 65.0, 10.0, 55.0, 20.0, 142.50),
            ]
            for wh_code, wh_name, bin_loc, on_hand, reserved, avail, safety, cost in inv_pmp290:
                inv_id = get_deterministic_uuid(f"erp_inv_{p_no}", wh_code)
                cursor.execute(
                    """
                    INSERT INTO erp_inventory (
                        id, part_number, warehouse_code, warehouse_name, bin_location,
                        quantity_on_hand, quantity_reserved, quantity_available,
                        safety_stock, unit_cost, currency, last_counted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?)
                    """,
                    (inv_id, p_no, wh_code, wh_name, bin_loc, on_hand, reserved, avail, safety, cost, "2025-02-01T08:00:00"),
                )
                erp_inventory_count += 1
        else:
            wh_indices = [0] if idx % 2 == 0 else [0, 1]
            for w_idx in wh_indices:
                wh_code, wh_name, _ = warehouses[w_idx]
                bin_loc = f"{chr(65 + (idx % 6))}-{10 + (idx % 20):02d}-{1 + (idx % 8):02d}"
                on_hand = float(20 + (idx * 7) % 150)
                reserved = float((idx * 3) % int(max(1, on_hand * 0.4)))
                avail = on_hand - reserved
                safety = float(10 + (idx % 25))
                inv_id = get_deterministic_uuid(f"erp_inv_{p_no}", wh_code)
                cursor.execute(
                    """
                    INSERT INTO erp_inventory (
                        id, part_number, warehouse_code, warehouse_name, bin_location,
                        quantity_on_hand, quantity_reserved, quantity_available,
                        safety_stock, unit_cost, currency, last_counted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?)
                    """,
                    (inv_id, p_no, wh_code, wh_name, bin_loc, on_hand, reserved, avail, safety, base_cost, "2025-01-30T12:00:00"),
                )
                erp_inventory_count += 1

    erp_pos = [
        ("PO-2025-0812", 1, "PMP-0290", "John Crane Mechanical Seals", 500.0, 0.0, 142.50, "2025-01-20T08:00:00", "2025-02-15T12:00:00", "IN_TRANSIT"),
        ("PO-2025-0955", 1, "PMP-0290", "SKF Bearing Group", 250.0, 0.0, 140.00, "2025-01-25T10:30:00", "2025-03-01T17:00:00", "OPEN"),
        ("PO-2025-0101", 1, "PMP-0006", "Swagelok Fluid Systems", 100.0, 100.0, 85.00, "2025-01-05T09:00:00", "2025-01-25T12:00:00", "RECEIVED"),
        ("PO-2025-0204", 1, "PMP-0018", "Flowserve Fluid Motion", 200.0, 0.0, 12.50, "2025-01-18T11:00:00", "2025-02-28T12:00:00", "OPEN"),
        ("PO-2025-0315", 1, "PMP-0088", "Parker Hannifin Seal Group", 400.0, 0.0, 8.20, "2025-01-22T14:00:00", "2025-02-20T12:00:00", "IN_TRANSIT"),
    ]

    for po_no, line_no, p_no, sup_name, q_ord, q_rec, u_pr, o_date, exp_date, po_stat in erp_pos:
        po_id = get_deterministic_uuid("erp_po", f"{po_no}_{line_no}")
        cursor.execute(
            """
            INSERT INTO erp_purchase_orders (
                id, po_number, line_number, part_number, supplier_name,
                quantity_ordered, quantity_received, unit_price, currency,
                order_date, expected_delivery, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, ?)
            """,
            (po_id, po_no, line_no, p_no, sup_name, q_ord, q_rec, u_pr, o_date, exp_date, po_stat, o_date),
        )

    # =========================================================================
    # 8. GENERATE QMS DEFECT REPORTS
    # =========================================================================
    qms_defects = [
        (
            "DEF-2025-0042", "PMP-0290",
            "High-Frequency Vibration & Roller Skewing under Dynamic Peak Load",
            "Severe outer raceway spalling and cage fracture detected on ApexFlow 1000 units during continuous slurry pumping. Accelerated fatigue initiated by localized subsurface shear stresses under peak hydraulic head.",
            "CRITICAL", "UNDER_INVESTIGATION", "SURFACE_SPALLING",
            "Dynamic radial load rating of 25mm bearing is insufficient during peak discharge head conditions; localized roller micro-cracking propagates into flaking.",
            ["SN-APX-2025-001", "SN-APX-2025-004"],
            "Field Reliability Engineering (Sarah Jenkins, PE)",
            "Quarantine warehouse stock of PMP-0290 batch 2025-Q1 and freeze in-transit PO-2025-0812. Issue urgent ECR to up-rate bearing assembly.",
            "2025-02-01T14:30:00", "2025-02-02T09:15:00",
        ),
        (
            "DEF-2025-0038", "PMP-0018",
            "RoHS Non-Compliance: Excessive Lead in Brass Plug",
            "Incoming inspection XRF spectroscopy detected Pb concentration exceeding 4.2% wt, violating EU RoHS 2011/65/EU limit of 0.1% wt.",
            "MAJOR", "OPEN", "MATERIAL_NON_COMPLIANCE",
            "Supplier substituted free-machining brass UNS C36000 instead of eco-brass specification.",
            [],
            "Incoming Quality Control (Marcus Vance)",
            "Lot rejected at dock; quarantine pending supplier RMA.",
            "2025-01-28T10:00:00", "2025-01-28T16:00:00",
        ),
        (
            "DEF-2025-0029", "PMP-0088",
            "O-Ring Compression Set Failure under High Temperature",
            "Viton FKM O-ring exhibited permanent deformation and fluid weeping during hydrostatic test cell validation at 140C.",
            "MINOR", "RESOLVED", "THERMAL_DEGRADATION",
            "Exceeded continuous thermal limit of standard FKM formulation.",
            ["SN-APX-2025-002"],
            "Test Cell Supervisor (David Chen)",
            "Replaced with AFLAS fluoroelastomer seal; hydrotest passed.",
            "2025-01-15T11:20:00", "2025-01-18T17:00:00",
        ),
    ]

    for def_no, p_no, title, desc, sev, stat, f_mode, r_cause, serials, rep_by, cont, c_at, u_at in qms_defects:
        qms_id = get_deterministic_uuid("qms_defect", def_no)
        cursor.execute(
            """
            INSERT INTO qms_defect_reports (
                id, defect_number, part_number, title, description,
                severity, status, failure_mode, root_cause, linked_serial_numbers,
                reported_by, containment_action, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                qms_id, def_no, p_no, title, desc, sev, stat, f_mode,
                r_cause, json.dumps(serials), rep_by, cont, c_at, u_at
            ),
        )

    # =========================================================================
    # 9. GENERATE IIOT DEVICES & SENSOR FAILURE EVENTS
    # =========================================================================
    iiot_devices = [
        (
            "EDGE-GATEWAY-101", "SN-APX-2025-001",
            "ApexFlow 1000 - Unit #1 (Site Alpha)",
            "Permian Basin Refinery Unit 4B - Texas",
            ["PMP-0001", "PMP-0010", "PMP-0290"],
            "CRITICAL", "2025-02-02T10:00:00"
        ),
        (
            "EDGE-GATEWAY-102", "SN-APX-2025-002",
            "ApexFlow 1000 - Unit #2 (Site Beta)",
            "Rotterdam Chemical Processing Terminal",
            ["PMP-0001", "PMP-0010"],
            "ONLINE", "2025-02-02T10:00:00"
        ),
        (
            "EDGE-GATEWAY-103", "SN-APX-2025-003",
            "MagDrive 5000 - Unit #1 (Site Gamma)",
            "Singapore Petrochemical Complex",
            ["PMP-0005"],
            "ONLINE", "2025-02-02T10:00:00"
        ),
        (
            "EDGE-GATEWAY-104", "SN-APX-2025-004",
            "ApexFlow 1000 - Unit #4 (Site Delta)",
            "Alberta Oil Sands Pumping Station",
            ["PMP-0001", "PMP-0290"],
            "WARNING", "2025-02-02T10:00:00"
        ),
    ]

    for d_id, sn, a_name, loc, inst_parts, dev_stat, l_ping in iiot_devices:
        dev_row_id = get_deterministic_uuid("iiot_dev", d_id)
        cursor.execute(
            """
            INSERT INTO iiot_devices (
                id, device_id, serial_number, asset_name, location,
                installed_parts, status, last_ping
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (dev_row_id, d_id, sn, a_name, loc, json.dumps(inst_parts), dev_stat, l_ping),
        )

    iiot_events = [
        (
            "EVT-IIOT-2025-0901", "EDGE-GATEWAY-101", "SN-APX-2025-001", "PMP-0290",
            "VIBRATION", "radial_vibration_velocity_rms", 18.6, "mm/s", 4.5,
            "CRITICAL", "THRESHOLD_EXCEEDED", "2025-02-02T08:14:22",
            "Bearing drive-end radial vibration exceeded ISO 10816-3 Zone D trip limit (18.6 mm/s vs 4.5 mm/s limit). FFT spectrum confirms cage frequency harmonics and roller defect frequency BPFO peaks."
        ),
        (
            "EVT-IIOT-2025-0902", "EDGE-GATEWAY-101", "SN-APX-2025-001", "PMP-0290",
            "TEMPERATURE", "bearing_outer_race_temp", 114.5, "deg_C", 80.0,
            "CRITICAL", "RAPID_DEGRADATION", "2025-02-02T08:22:05",
            "Bearing housing temperature rose 34.5 deg C above alarm limit in 45 minutes; lubricant thermal breakdown suspected."
        ),
        (
            "EVT-IIOT-2025-0903", "EDGE-GATEWAY-101", "SN-APX-2025-001", "PMP-0290",
            "ACOUSTIC", "ultrasonic_emission_peak", 89.2, "dB", 65.0,
            "WARNING", "TREND_ANOMALY", "2025-02-02T07:45:10",
            "High-frequency acoustic emission indicating micro-impacts between rollers and flaked raceway."
        ),
        (
            "EVT-IIOT-2025-0904", "EDGE-GATEWAY-104", "SN-APX-2025-004", "PMP-0290",
            "VIBRATION", "radial_vibration_velocity_rms", 6.8, "mm/s", 4.5,
            "WARNING", "THRESHOLD_EXCEEDED", "2025-02-02T09:10:00",
            "Elevated drive-end bearing vibration observed during high-flow duty cycle."
        ),
        (
            "EVT-IIOT-2025-0905", "EDGE-GATEWAY-102", "SN-APX-2025-002", "PMP-0010",
            "TEMPERATURE", "shaft_bearing_temp", 58.2, "deg_C", 80.0,
            "INFO", "NOMINAL_TELEMETRY", "2025-02-02T09:30:00",
            "Shaft operating temperatures nominal under steady state operation."
        ),
    ]

    for ev_id, d_id, sn, p_no, s_type, m_name, m_val, unit, thresh, sev, ev_type, t_stamp, details in iiot_events:
        evt_row_id = get_deterministic_uuid("iiot_evt", ev_id)
        cursor.execute(
            """
            INSERT INTO iiot_sensor_events (
                id, event_id, device_id, serial_number, part_number,
                sensor_type, metric_name, metric_value, unit, threshold_value,
                severity, event_type, timestamp, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evt_row_id, ev_id, d_id, sn, p_no, s_type, m_name,
                m_val, unit, thresh, sev, ev_type, t_stamp, details
            ),
        )
    conn.commit()

    conn.execute("PRAGMA foreign_keys = ON;")
    conn.close()

    summary = {
        "status": "success",
        "database": db_path,
        "parts_count": len(parts),
        "suppliers_count": len(suppliers),
        "manufacturer_parts_count": len(mfr_parts),
        "bom_links_count": len(bom_links),
        "documents_count": len(doc_titles),
        "change_requests_count": len(cr_data),
        "erp_inventory_records": erp_inventory_count,
        "erp_purchase_orders_count": len(erp_pos),
        "qms_defects_count": len(qms_defects),
        "iiot_devices_count": len(iiot_devices),
        "iiot_sensor_events_count": len(iiot_events),
        "planted_issues": {
            "duplicate_parts_count": len(duplicate_pairs) * 2,
            "obsolete_parts_in_released_boms": len(obsolete_usages),
            "buy_parts_with_no_supplier": len(no_supplier_buy_indices),
            "ebom_mbom_mismatches": 5,
            "rohs_non_compliant_parts": len(rohs_non_compliant_map),
        }
    }
    return summary


def main():
    parser = argparse.ArgumentParser(description="Deterministic Mock PLM Dataset Generator")
    parser.add_argument("--db-path", default="plm_mock.db", help="Target SQLite database file")
    args = parser.parse_args()

    print(f"Generating deterministic PLM mock dataset into '{args.db_path}' (seed={RANDOM_SEED})...")
    res = generate_dataset(db_path=args.db_path)
    print("Dataset generation completed successfully!")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
