"""Seed data generator for Mock PLM system."""

from plm_mcp.backend.mock.backend import MockBackend
from plm_mcp.models import (
    ChangeCategory,
    ChangePriority,
    DocType,
    ItemDisposition,
    LifecycleState,
    PartDocLinkType,
    SourcingStatus,
)


def seed_mock_data(backend: MockBackend) -> None:
    """Populates the MockBackend with realistic multi-level Drone engineering data."""
    # Check if already seeded
    existing_parts = backend.search_parts()
    if existing_parts:
        return

    # 1. Create Parts
    # Top-level Assembly
    backend.create_part(
        part_number="DRN-1000",
        name="AeroDrone X4 Quadcopter Assembly",
        description="Autonomous 4-rotor quadcopter drone complete assembly.",
    )
    backend.iterate_part("DRN-1000", description="Initial layout draft")
    backend.set_part_lifecycle_state("DRN-1000", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-1000", LifecycleState.RELEASED)

    # Airframe Subassembly
    backend.create_part(
        part_number="DRN-2000",
        name="Airframe & Chassis Subassembly",
        description="Rigid carbon-fiber structural chassis.",
    )
    backend.set_part_lifecycle_state("DRN-2000", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-2000", LifecycleState.RELEASED)

    backend.create_part(
        part_number="DRN-2010",
        name="Carbon Fiber Upper Plate",
        description="2mm 3K twill carbon fiber top deck.",
    )
    backend.set_part_lifecycle_state("DRN-2010", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-2010", LifecycleState.RELEASED)

    backend.create_part(
        part_number="DRN-2020",
        name="Carbon Fiber Lower Plate",
        description="3mm 3K twill carbon fiber bottom deck.",
    )
    backend.set_part_lifecycle_state("DRN-2020", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-2020", LifecycleState.RELEASED)

    backend.create_part(
        part_number="DRN-2030",
        name="Motor Arm 250mm",
        description="Reinforced carbon fiber cantilever motor arm.",
    )
    backend.set_part_lifecycle_state("DRN-2030", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-2030", LifecycleState.RELEASED)

    backend.create_part(
        part_number="FST-0001",
        name="M3x8mm Titanium Hex Screw",
        description="Grade 5 aerospace titanium fastener.",
    )
    backend.set_part_lifecycle_state("FST-0001", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("FST-0001", LifecycleState.RELEASED)

    # Propulsion Subassembly
    backend.create_part(
        part_number="DRN-3000",
        name="Propulsion System Subassembly",
        description="Motors, speed controllers, and propeller set.",
    )
    backend.set_part_lifecycle_state("DRN-3000", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-3000", LifecycleState.RELEASED)

    backend.create_part(
        part_number="DRN-3010",
        name="2207 1800KV Brushless Motor",
        description="High efficiency outrunner motor for 6S LiPo.",
    )
    backend.set_part_lifecycle_state("DRN-3010", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-3010", LifecycleState.RELEASED)

    backend.create_part(
        part_number="DRN-3020",
        name="35A 4-in-1 ESC Controller",
        description="Electronic speed controller supporting DShot600.",
    )
    backend.set_part_lifecycle_state("DRN-3020", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-3020", LifecycleState.RELEASED)

    backend.create_part(
        part_number="DRN-3030",
        name="5-inch Tri-Blade Propeller CW/CCW",
        description="Polycarbonate high-durability aerodynamic blades.",
    )
    backend.set_part_lifecycle_state("DRN-3030", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-3030", LifecycleState.RELEASED)

    # Avionics Subassembly (Revised to B.1 In Work)
    backend.create_part(
        part_number="DRN-4000",
        name="Flight Avionics Unit",
        description="Flight management computer, sensors, and GPS.",
    )
    backend.set_part_lifecycle_state("DRN-4000", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-4000", LifecycleState.RELEASED)
    backend.revise_part("DRN-4000", description="Revision B for next-gen telemetry")

    backend.create_part(
        part_number="DRN-4010",
        name="F7 Flight Controller PCB",
        description="STM32F722 processor running ArduPilot/Betaflight.",
    )
    backend.set_part_lifecycle_state("DRN-4010", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-4010", LifecycleState.RELEASED)
    backend.revise_part("DRN-4010", description="Upgraded IMU to BMI270")

    backend.create_part(
        part_number="DRN-4020",
        name="GPS / Compass Module",
        description="Multi-constellation GNSS with magnetometer.",
    )
    backend.set_part_lifecycle_state("DRN-4020", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-4020", LifecycleState.RELEASED)

    backend.create_part(
        part_number="DRN-4030",
        name="FPV HD Camera Module",
        description="Digital low-latency 1080p camera.",
    )
    backend.set_part_lifecycle_state("DRN-4030", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-4030", LifecycleState.RELEASED)

    # 2. Build BOM Usage Links
    # Top assembly -> subassemblies
    # Note: to add BOM links to DRN-1000, we revise it to B.1 or add while in work.
    # For initial seed simplicity, we create temporary In Work revisions or insert links directly.
    # To demonstrate BOM building cleanly through backend API:
    # Let's iterate/revise DRN-1000 to add components, then release it:
    backend.revise_part("DRN-1000", description="BOM consolidation revision B")
    backend.add_bom_component("DRN-1000", "DRN-2000", quantity=1.0, find_number=10, notes="Structural chassis")
    backend.add_bom_component("DRN-1000", "DRN-3000", quantity=1.0, find_number=20, notes="Drive powertrain")
    backend.add_bom_component("DRN-1000", "DRN-4000", quantity=1.0, find_number=30, notes="Avionics stack")
    backend.set_part_lifecycle_state("DRN-1000", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-1000", LifecycleState.RELEASED)

    # Airframe BOM
    backend.revise_part("DRN-2000", description="BOM integration")
    backend.add_bom_component("DRN-2000", "DRN-2010", quantity=1.0, find_number=10)
    backend.add_bom_component("DRN-2000", "DRN-2020", quantity=1.0, find_number=20)
    backend.add_bom_component("DRN-2000", "DRN-2030", quantity=4.0, find_number=30, ref_designators="ARM-FL, ARM-FR, ARM-RL, ARM-RR")
    backend.add_bom_component("DRN-2000", "FST-0001", quantity=16.0, find_number=40, notes="Arm fasteners")
    backend.set_part_lifecycle_state("DRN-2000", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-2000", LifecycleState.RELEASED)

    # Propulsion BOM
    backend.revise_part("DRN-3000", description="BOM integration")
    backend.add_bom_component("DRN-3000", "DRN-3010", quantity=4.0, find_number=10, ref_designators="M1, M2, M3, M4")
    backend.add_bom_component("DRN-3000", "DRN-3020", quantity=1.0, find_number=20, ref_designators="ESC1")
    backend.add_bom_component("DRN-3000", "DRN-3030", quantity=4.0, find_number=30, ref_designators="PROP-1, PROP-2, PROP-3, PROP-4")
    backend.set_part_lifecycle_state("DRN-3000", LifecycleState.UNDER_REVIEW)
    backend.set_part_lifecycle_state("DRN-3000", LifecycleState.RELEASED)

    # Avionics BOM (stays In Work at B.1)
    backend.add_bom_component("DRN-4000", "DRN-4010", quantity=1.0, find_number=10, ref_designators="FC1")
    backend.add_bom_component("DRN-4000", "DRN-4020", quantity=1.0, find_number=20, ref_designators="GPS1")
    backend.add_bom_component("DRN-4000", "DRN-4030", quantity=1.0, find_number=30, ref_designators="CAM1")

    # 3. Documents & Links
    backend.create_document(
        doc_number="DOC-SPEC-1000",
        name="AeroDrone System Engineering Specification",
        doc_type=DocType.SPECIFICATION,
        file_name="AeroDrone_SysSpec_v1.pdf",
        file_size_bytes=2450000,
        mime_type="application/pdf",
    )
    backend.link_document_to_part("DRN-1000", "DOC-SPEC-1000", PartDocLinkType.DESCRIBES)

    backend.create_document(
        doc_number="DOC-CAD-2000",
        name="Airframe 3D CAD Assembly",
        doc_type=DocType.CAD_DRAWING,
        file_name="Airframe_Assembly.prt",
        file_size_bytes=15800000,
        mime_type="application/x-creo-prt",
    )
    backend.link_document_to_part("DRN-2000", "DOC-CAD-2000", PartDocLinkType.DESCRIBES)

    backend.create_document(
        doc_number="DOC-TR-3000",
        name="Motor Thrust & Thermal Bench Test Report",
        doc_type=DocType.TEST_REPORT,
        file_name="Test_Report_Thrust_2207.pdf",
        file_size_bytes=1200000,
        mime_type="application/pdf",
    )
    backend.link_document_to_part("DRN-3000", "DOC-TR-3000", PartDocLinkType.REFERENCES)

    # 4. Change Management
    cr = backend.create_change_request(
        title="Upgrade Flight Controller IMU & Processor",
        description="Address supply chain obsolescence on F4 MCU by migrating to STM32F7 with low-noise BMI270 IMU.",
        category=ChangeCategory.DESIGN_IMPROVEMENT,
        priority=ChangePriority.HIGH,
        affected_parts=["DRN-4000", "DRN-4010"],
    )

    cn = backend.create_change_notice(
        title="Implement Avionics Revision B Migration",
        description="Transition flight controller assembly to Rev B.1 and disposition older Rev A units.",
        cr_number=cr.cr_number,
    )
    backend.add_change_affected_item(
        cn_number=cn.cn_number,
        item_type="PART",
        item_number="DRN-4010",
        disposition=ItemDisposition.REWORK,
    )

    # 5. Suppliers & AML
    backend.add_manufacturer("T-Motor Tech Co.", cage_code="7TM01", country="China")
    backend.add_manufacturer("Holybro Electronics", cage_code="8HB02", country="Hong Kong")
    backend.add_manufacturer("Fastenal Aerospace", cage_code="1FST3", country="USA")

    backend.set_sourcing_link(
        part_number="DRN-3010",
        mfr_name="T-Motor Tech Co.",
        mfr_part_number="F60-PRO-IV-1750KV",
        status=SourcingStatus.PREFERRED,
        preference_rank=1,
    )
    backend.set_sourcing_link(
        part_number="DRN-4010",
        mfr_name="Holybro Electronics",
        mfr_part_number="KAKUTE-F7-V1.5",
        status=SourcingStatus.APPROVED,
        preference_rank=1,
    )
    backend.set_sourcing_link(
        part_number="FST-0001",
        mfr_name="Fastenal Aerospace",
        mfr_part_number="MS51957-26",
        status=SourcingStatus.PREFERRED,
        preference_rank=1,
    )

