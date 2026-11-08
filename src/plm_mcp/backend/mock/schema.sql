-- SQLite DDL Schema for Mock PLM (Windchill-style)

CREATE TABLE IF NOT EXISTS part_masters (
    id TEXT PRIMARY KEY,
    part_number TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS part_versions (
    id TEXT PRIMARY KEY,
    master_id TEXT NOT NULL,
    revision TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    lifecycle_state TEXT NOT NULL,
    description TEXT,
    make_buy TEXT NOT NULL DEFAULT 'MAKE',
    material TEXT DEFAULT '',
    created_by TEXT NOT NULL DEFAULT 'wcadmin',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (master_id) REFERENCES part_masters(id) ON DELETE CASCADE,
    UNIQUE (master_id, revision, iteration)
);

CREATE TABLE IF NOT EXISTS bom_links (
    id TEXT PRIMARY KEY,
    parent_version_id TEXT NOT NULL,
    child_master_id TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 1.0,
    unit TEXT NOT NULL DEFAULT 'ea',
    find_number INTEGER,
    ref_designators TEXT,
    bom_type TEXT NOT NULL DEFAULT 'EBOM',
    notes TEXT DEFAULT '',
    FOREIGN KEY (parent_version_id) REFERENCES part_versions(id) ON DELETE CASCADE,
    FOREIGN KEY (child_master_id) REFERENCES part_masters(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS document_masters (
    id TEXT PRIMARY KEY,
    doc_number TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_versions (
    id TEXT PRIMARY KEY,
    master_id TEXT NOT NULL,
    revision TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    lifecycle_state TEXT NOT NULL,
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

CREATE TABLE IF NOT EXISTS part_doc_links (
    id TEXT PRIMARY KEY,
    part_version_id TEXT NOT NULL,
    doc_version_id TEXT NOT NULL,
    link_type TEXT NOT NULL DEFAULT 'DESCRIBES',
    FOREIGN KEY (part_version_id) REFERENCES part_versions(id) ON DELETE CASCADE,
    FOREIGN KEY (doc_version_id) REFERENCES document_versions(id) ON DELETE CASCADE,
    UNIQUE (part_version_id, doc_version_id, link_type)
);

CREATE TABLE IF NOT EXISTS change_requests (
    id TEXT PRIMARY KEY,
    cr_number TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    state TEXT NOT NULL,
    affected_parts TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS change_notices (
    id TEXT PRIMARY KEY,
    cn_number TEXT UNIQUE NOT NULL,
    change_request_id TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (change_request_id) REFERENCES change_requests(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS change_affected_items (
    id TEXT PRIMARY KEY,
    change_notice_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    item_number TEXT NOT NULL,
    version_label TEXT NOT NULL,
    disposition TEXT NOT NULL,
    FOREIGN KEY (change_notice_id) REFERENCES change_notices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS change_resulting_items (
    id TEXT PRIMARY KEY,
    change_notice_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    item_number TEXT NOT NULL,
    target_version_label TEXT NOT NULL,
    target_state TEXT NOT NULL,
    FOREIGN KEY (change_notice_id) REFERENCES change_notices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS manufacturers (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    cage_code TEXT,
    status TEXT NOT NULL,
    country TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS manufacturer_parts (
    id TEXT PRIMARY KEY,
    manufacturer_id TEXT NOT NULL,
    mfr_part_number TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (manufacturer_id) REFERENCES manufacturers(id) ON DELETE CASCADE,
    UNIQUE (manufacturer_id, mfr_part_number)
);

CREATE TABLE IF NOT EXISTS aml_links (
    id TEXT PRIMARY KEY,
    part_master_id TEXT NOT NULL,
    mfr_part_id TEXT NOT NULL,
    sourcing_status TEXT NOT NULL,
    preference_rank INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (part_master_id) REFERENCES part_masters(id) ON DELETE CASCADE,
    FOREIGN KEY (mfr_part_id) REFERENCES manufacturer_parts(id) ON DELETE CASCADE,
    UNIQUE (part_master_id, mfr_part_id)
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_part_versions_master ON part_versions(master_id);
CREATE INDEX IF NOT EXISTS idx_bom_parent ON bom_links(parent_version_id);
CREATE INDEX IF NOT EXISTS idx_bom_child ON bom_links(child_master_id);
CREATE INDEX IF NOT EXISTS idx_doc_versions_master ON document_versions(master_id);
CREATE INDEX IF NOT EXISTS idx_aml_part ON aml_links(part_master_id);

