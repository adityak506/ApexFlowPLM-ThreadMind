-- ============================================================================
-- SQLite Relational Schema for Mock PLM System (Windchill-Style)
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- Part Masters: Identity of parts across all versions
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS part_masters (
    id TEXT PRIMARY KEY,
    part_number TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- Part Versions: Revision and Iteration instances (e.g. A.1, A.2, B.1)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS part_versions (
    id TEXT PRIMARY KEY,
    master_id TEXT NOT NULL,
    revision TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('IN_WORK', 'UNDER_REVIEW', 'RELEASED', 'OBSOLETE')),
    description TEXT DEFAULT '',
    make_buy TEXT NOT NULL DEFAULT 'MAKE' CHECK(make_buy IN ('MAKE', 'BUY')),
    material TEXT DEFAULT '',
    created_by TEXT NOT NULL DEFAULT 'wcadmin',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (master_id) REFERENCES part_masters(id) ON DELETE CASCADE,
    UNIQUE (master_id, revision, iteration)
);

-- ----------------------------------------------------------------------------
-- BOM Links: Parent-to-child usage links (WTPartUsageLink equivalent)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bom_links (
    id TEXT PRIMARY KEY,
    parent_version_id TEXT NOT NULL,
    child_master_id TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 1.0,
    unit TEXT NOT NULL DEFAULT 'ea',
    find_number INTEGER,
    ref_designators TEXT,
    bom_type TEXT NOT NULL DEFAULT 'EBOM' CHECK(bom_type IN ('EBOM', 'MBOM')),
    notes TEXT DEFAULT '',
    FOREIGN KEY (parent_version_id) REFERENCES part_versions(id) ON DELETE CASCADE,
    FOREIGN KEY (child_master_id) REFERENCES part_masters(id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- Document Masters: Identity of documents across versions
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_masters (
    id TEXT PRIMARY KEY,
    doc_number TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    doc_type TEXT NOT NULL CHECK(doc_type IN ('SPECIFICATION', 'CAD_DRAWING', 'TEST_REPORT', 'USER_MANUAL')),
    created_at TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- Document Versions: Specific revisions of documents and vault attachments
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS document_versions (
    id TEXT PRIMARY KEY,
    master_id TEXT NOT NULL,
    revision TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    lifecycle_state TEXT NOT NULL CHECK(lifecycle_state IN ('IN_WORK', 'UNDER_REVIEW', 'RELEASED', 'OBSOLETE')),
    file_name TEXT,
    file_size_bytes INTEGER,
    mime_type TEXT,
    file_uri TEXT,
    created_by TEXT NOT NULL DEFAULT 'wcadmin',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (master_id) REFERENCES document_masters(id) ON DELETE CASCADE,
    UNIQUE (master_id, revision, iteration)
);

-- ----------------------------------------------------------------------------
-- Part-Document Associations: Describes / References links
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS part_doc_links (
    id TEXT PRIMARY KEY,
    part_version_id TEXT NOT NULL,
    doc_version_id TEXT NOT NULL,
    link_type TEXT NOT NULL DEFAULT 'DESCRIBES' CHECK(link_type IN ('DESCRIBES', 'REFERENCES')),
    FOREIGN KEY (part_version_id) REFERENCES part_versions(id) ON DELETE CASCADE,
    FOREIGN KEY (doc_version_id) REFERENCES document_versions(id) ON DELETE CASCADE,
    UNIQUE (part_version_id, doc_version_id, link_type)
);

-- ----------------------------------------------------------------------------
-- Change Requests: Engineering Change Requests (ECR)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS change_requests (
    id TEXT PRIMARY KEY,
    cr_number TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('DESIGN_IMPROVEMENT', 'DEFECT', 'COST_REDUCTION', 'COMPLIANCE')),
    priority TEXT NOT NULL CHECK(priority IN ('LOW', 'MEDIUM', 'HIGH', 'EMERGENCY')),
    state TEXT NOT NULL CHECK(state IN ('OPEN', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'RESOLVED')),
    affected_parts TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- Change Notices: Engineering Change Notices (ECN)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS change_notices (
    id TEXT PRIMARY KEY,
    cn_number TEXT UNIQUE NOT NULL,
    change_request_id TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('OPEN', 'IN_WORK', 'UNDER_REVIEW', 'APPROVED', 'COMPLETED', 'CANCELLED')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (change_request_id) REFERENCES change_requests(id) ON DELETE SET NULL
);

-- ----------------------------------------------------------------------------
-- Change Affected Items: Items impacted by ECN with disposition directive
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS change_affected_items (
    id TEXT PRIMARY KEY,
    change_notice_id TEXT NOT NULL,
    item_type TEXT NOT NULL CHECK(item_type IN ('PART', 'DOCUMENT')),
    item_number TEXT NOT NULL,
    version_label TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK(disposition IN ('SCRAP', 'REWORK', 'USE_AS_IS')),
    FOREIGN KEY (change_notice_id) REFERENCES change_notices(id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- Change Resulting Items: Items created/released by ECN
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS change_resulting_items (
    id TEXT PRIMARY KEY,
    change_notice_id TEXT NOT NULL,
    item_type TEXT NOT NULL CHECK(item_type IN ('PART', 'DOCUMENT')),
    item_number TEXT NOT NULL,
    target_version_label TEXT NOT NULL,
    target_state TEXT NOT NULL,
    FOREIGN KEY (change_notice_id) REFERENCES change_notices(id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- Manufacturers / Suppliers: Vendor organizations
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS manufacturers (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    cage_code TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'INACTIVE', 'RESTRICTED')),
    country TEXT NOT NULL DEFAULT 'USA',
    created_at TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- Manufacturer Parts: External catalog items
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS manufacturer_parts (
    id TEXT PRIMARY KEY,
    manufacturer_id TEXT NOT NULL,
    mfr_part_number TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(id) ON DELETE CASCADE,
    UNIQUE (manufacturer_id, mfr_part_number)
);

-- ----------------------------------------------------------------------------
-- AML Links: Approved Manufacturer List associations (AXLLink equivalent)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS aml_links (
    id TEXT PRIMARY KEY,
    part_master_id TEXT NOT NULL,
    mfr_part_id TEXT NOT NULL,
    sourcing_status TEXT NOT NULL CHECK(sourcing_status IN ('PREFERRED', 'APPROVED', 'DO_NOT_USE', 'UNDER_REVIEW')),
    preference_rank INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (part_master_id) REFERENCES part_masters(id) ON DELETE CASCADE,
    FOREIGN KEY (mfr_part_id) REFERENCES manufacturer_parts(id) ON DELETE CASCADE,
    UNIQUE (part_master_id, mfr_part_id)
);

-- ----------------------------------------------------------------------------
-- Performance Indexes
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_part_versions_master ON part_versions(master_id);
CREATE INDEX IF NOT EXISTS idx_part_versions_state ON part_versions(lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_bom_parent ON bom_links(parent_version_id);
CREATE INDEX IF NOT EXISTS idx_bom_child ON bom_links(child_master_id);
CREATE INDEX IF NOT EXISTS idx_doc_versions_master ON document_versions(master_id);
CREATE INDEX IF NOT EXISTS idx_part_doc_part ON part_doc_links(part_version_id);
CREATE INDEX IF NOT EXISTS idx_part_doc_doc ON part_doc_links(doc_version_id);
CREATE INDEX IF NOT EXISTS idx_aml_part ON aml_links(part_master_id);
CREATE INDEX IF NOT EXISTS idx_aml_mfr_part ON aml_links(mfr_part_id);

-- ============================================================================
-- Enterprise Resource Planning (ERP) Mock Schema
-- ============================================================================

-- ----------------------------------------------------------------------------
-- ERP Inventory: Warehouse stock levels per part
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp_inventory (
    id TEXT PRIMARY KEY,
    part_number TEXT NOT NULL,
    warehouse_code TEXT NOT NULL,
    warehouse_name TEXT NOT NULL,
    bin_location TEXT NOT NULL,
    quantity_on_hand REAL NOT NULL DEFAULT 0.0,
    quantity_reserved REAL NOT NULL DEFAULT 0.0,
    quantity_available REAL NOT NULL DEFAULT 0.0,
    safety_stock REAL NOT NULL DEFAULT 0.0,
    unit_cost REAL NOT NULL DEFAULT 0.0,
    currency TEXT NOT NULL DEFAULT 'USD',
    last_counted TEXT NOT NULL,
    FOREIGN KEY (part_number) REFERENCES part_masters(part_number) ON DELETE CASCADE,
    UNIQUE (part_number, warehouse_code)
);

-- ----------------------------------------------------------------------------
-- ERP Purchase Orders: External procurement orders and supplier shipments
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp_purchase_orders (
    id TEXT PRIMARY KEY,
    po_number TEXT NOT NULL,
    line_number INTEGER NOT NULL DEFAULT 1,
    part_number TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    quantity_ordered REAL NOT NULL,
    quantity_received REAL NOT NULL DEFAULT 0.0,
    unit_price REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    order_date TEXT NOT NULL,
    expected_delivery TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('OPEN', 'IN_TRANSIT', 'RECEIVED', 'CANCELLED', 'HOLD')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (part_number) REFERENCES part_masters(part_number) ON DELETE CASCADE,
    UNIQUE (po_number, line_number)
);

CREATE INDEX IF NOT EXISTS idx_erp_inv_part ON erp_inventory(part_number);
CREATE INDEX IF NOT EXISTS idx_erp_po_part ON erp_purchase_orders(part_number);
CREATE INDEX IF NOT EXISTS idx_erp_po_status ON erp_purchase_orders(status);

-- ============================================================================
-- Quality Management System (QMS) Mock Schema
-- ============================================================================

-- ----------------------------------------------------------------------------
-- QMS Defect Reports: Non-conformance reports (NCR) and failure records
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qms_defect_reports (
    id TEXT PRIMARY KEY,
    defect_number TEXT UNIQUE NOT NULL,
    part_number TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('CRITICAL', 'MAJOR', 'MINOR')),
    status TEXT NOT NULL CHECK(status IN ('OPEN', 'UNDER_INVESTIGATION', 'CONTAINED', 'RESOLVED', 'CLOSED')),
    failure_mode TEXT NOT NULL,
    root_cause TEXT DEFAULT '',
    linked_serial_numbers TEXT DEFAULT '[]',
    reported_by TEXT NOT NULL,
    containment_action TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (part_number) REFERENCES part_masters(part_number) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_qms_defect_part ON qms_defect_reports(part_number);
CREATE INDEX IF NOT EXISTS idx_qms_defect_severity ON qms_defect_reports(severity);
CREATE INDEX IF NOT EXISTS idx_qms_defect_status ON qms_defect_reports(status);

-- ============================================================================
-- Industrial Internet of Things (IIoT) Mock Schema
-- ============================================================================

-- ----------------------------------------------------------------------------
-- IIoT Edge Devices / Assets: Physical equipment tracked in the field
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS iiot_devices (
    id TEXT PRIMARY KEY,
    device_id TEXT UNIQUE NOT NULL,
    serial_number TEXT UNIQUE NOT NULL,
    asset_name TEXT NOT NULL,
    location TEXT NOT NULL,
    installed_parts TEXT DEFAULT '[]',
    status TEXT NOT NULL CHECK(status IN ('ONLINE', 'WARNING', 'CRITICAL', 'OFFLINE')),
    last_ping TEXT NOT NULL
);

-- ----------------------------------------------------------------------------
-- IIoT Sensor Events: High-frequency telemetry anomalies and failure events
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS iiot_sensor_events (
    id TEXT PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    device_id TEXT NOT NULL,
    serial_number TEXT NOT NULL,
    part_number TEXT NOT NULL,
    sensor_type TEXT NOT NULL CHECK(sensor_type IN ('VIBRATION', 'TEMPERATURE', 'PRESSURE', 'FLOW_RATE', 'ACOUSTIC')),
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    unit TEXT NOT NULL,
    threshold_value REAL NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('CRITICAL', 'WARNING', 'INFO')),
    event_type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    details TEXT DEFAULT '',
    FOREIGN KEY (part_number) REFERENCES part_masters(part_number) ON DELETE CASCADE,
    FOREIGN KEY (device_id) REFERENCES iiot_devices(device_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_iiot_events_part ON iiot_sensor_events(part_number);
CREATE INDEX IF NOT EXISTS idx_iiot_events_serial ON iiot_sensor_events(serial_number);
CREATE INDEX IF NOT EXISTS idx_iiot_events_severity ON iiot_sensor_events(severity);
CREATE INDEX IF NOT EXISTS idx_iiot_events_time ON iiot_sensor_events(timestamp);

