"""Mock SQLite backend implementing the PLMBackend interface."""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from plm_mcp.backend.base import PLMBackend
from plm_mcp.models import (
    AMLLink,
    BOMLink,
    BOMNode,
    ChangeAffectedItem,
    ChangeCategory,
    ChangeNotice,
    ChangeNoticeState,
    ChangePriority,
    ChangeRequest,
    ChangeRequestState,
    ChangeResultingItem,
    DocType,
    DocumentMaster,
    DocumentVersion,
    ItemDisposition,
    LifecycleState,
    Manufacturer,
    ManufacturerPart,
    ManufacturerStatus,
    PartDetail,
    PartDocLink,
    PartDocLinkType,
    PartMaster,
    PartSummary,
    PartVersion,
    SourcingStatus,
    WhereUsedItem,
)


class MockBackend(PLMBackend):
    """SQLite-backed implementation of the PLMBackend interface."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return self._conn

    def _init_db(self) -> None:
        schema_file = Path(__file__).parent / "schema.sql"
        with open(schema_file, "r", encoding="utf-8") as f:
            ddl = f.read()
        with self._get_connection() as conn:
            conn.executescript(ddl)
            conn.commit()

    def close(self) -> None:
        """Close connection."""
        if self._conn:
            self._conn.close()

    # -------------------------------------------------------------------------
    # Helper Utilities
    # -------------------------------------------------------------------------

    @staticmethod
    def _next_revision(rev: str) -> str:
        """Bump revision string: A -> B, Z -> AA."""
        if rev == "Z":
            return "AA"
        chars = list(rev)
        i = len(chars) - 1
        while i >= 0:
            if chars[i] == "Z":
                chars[i] = "A"
                i -= 1
            else:
                chars[i] = chr(ord(chars[i]) + 1)
                return "".join(chars)
        return "A" + "".join(chars)

    def _get_latest_part_version_row(
        self, conn: sqlite3.Connection, master_id: str
    ) -> sqlite3.Row | None:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM part_versions
            WHERE master_id = ?
            ORDER BY revision DESC, iteration DESC
            LIMIT 1
            """,
            (master_id,),
        )
        return cursor.fetchone()

    # -------------------------------------------------------------------------
    # Part Management
    # -------------------------------------------------------------------------

    def get_part(
        self, part_number: str, version: str | None = None
    ) -> PartDetail | None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM part_masters WHERE part_number = ?",
                (part_number,),
            )
            master_row = cursor.fetchone()
            if not master_row:
                return None

            master = PartMaster(
                id=master_row["id"],
                part_number=master_row["part_number"],
                name=master_row["name"],
                created_at=datetime.fromisoformat(master_row["created_at"]),
            )

            if version:
                # version expected as "A.1" or revision "A"
                if "." in version:
                    rev, it_str = version.split(".", 1)
                    cursor.execute(
                        """
                        SELECT * FROM part_versions
                        WHERE master_id = ? AND revision = ? AND iteration = ?
                        """,
                        (master.id, rev, int(it_str)),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM part_versions
                        WHERE master_id = ? AND revision = ?
                        ORDER BY iteration DESC LIMIT 1
                        """,
                        (master.id, version),
                    )
                version_row = cursor.fetchone()
            else:
                version_row = self._get_latest_part_version_row(conn, master.id)

            if not version_row:
                return None

            pv = PartVersion(
                id=version_row["id"],
                master_id=version_row["master_id"],
                part_number=master.part_number,
                name=master.name,
                revision=version_row["revision"],
                iteration=version_row["iteration"],
                version_label=f"{version_row['revision']}.{version_row['iteration']}",
                lifecycle_state=LifecycleState(version_row["lifecycle_state"]),
                description=version_row["description"] or "",
                created_by=version_row["created_by"],
                created_at=datetime.fromisoformat(version_row["created_at"]),
                updated_at=datetime.fromisoformat(version_row["updated_at"]),
            )

            # Association counts
            cursor.execute(
                "SELECT COUNT(*) as count FROM bom_links WHERE parent_version_id = ?",
                (pv.id,),
            )
            bom_count = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT COUNT(*) as count FROM part_doc_links WHERE part_version_id = ?",
                (pv.id,),
            )
            doc_count = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT COUNT(*) as count FROM aml_links WHERE part_master_id = ?",
                (master.id,),
            )
            aml_count = cursor.fetchone()["count"]

            return PartDetail(
                master=master,
                version=pv,
                bom_components_count=bom_count,
                documents_count=doc_count,
                aml_entries_count=aml_count,
            )

    def search_parts(
        self,
        query: str = "",
        lifecycle_state: str | None = None,
        limit: int = 20,
    ) -> list[PartSummary]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            q_pattern = f"%{query}%"

            sql = """
                SELECT m.part_number, m.name, v.revision, v.iteration,
                       v.lifecycle_state, v.description, v.updated_at
                FROM part_masters m
                JOIN part_versions v ON m.id = v.master_id
                WHERE (m.part_number LIKE ? OR m.name LIKE ? OR v.description LIKE ?)
                  AND v.id = (
                      SELECT id FROM part_versions
                      WHERE master_id = m.id
                      ORDER BY revision DESC, iteration DESC LIMIT 1
                  )
            """
            params: list[Any] = [q_pattern, q_pattern, q_pattern]

            if lifecycle_state:
                sql += " AND v.lifecycle_state = ?"
                params.append(lifecycle_state)

            sql += " ORDER BY m.part_number ASC LIMIT ?"
            params.append(limit)

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            return [
                PartSummary(
                    part_number=r["part_number"],
                    name=r["name"],
                    version_label=f"{r['revision']}.{r['iteration']}",
                    lifecycle_state=LifecycleState(r["lifecycle_state"]),
                    description=r["description"] or "",
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
                for r in rows
            ]

    def create_part(
        self, part_number: str, name: str, description: str = ""
    ) -> PartVersion:
        now_iso = datetime.utcnow().isoformat()
        master_id = str(uuid.uuid4())
        version_id = str(uuid.uuid4())

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO part_masters (id, part_number, name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (master_id, part_number, name, now_iso),
            )
            cursor.execute(
                """
                INSERT INTO part_versions (
                    id, master_id, revision, iteration, lifecycle_state,
                    description, created_by, created_at, updated_at
                ) VALUES (?, ?, 'A', 1, ?, ?, 'wcadmin', ?, ?)
                """,
                (
                    version_id,
                    master_id,
                    LifecycleState.IN_WORK.value,
                    description,
                    now_iso,
                    now_iso,
                ),
            )
            conn.commit()

        return PartVersion(
            id=version_id,
            master_id=master_id,
            part_number=part_number,
            name=name,
            revision="A",
            iteration=1,
            version_label="A.1",
            lifecycle_state=LifecycleState.IN_WORK,
            description=description,
            created_by="wcadmin",
        )

    def iterate_part(
        self, part_number: str, description: str = ""
    ) -> PartVersion:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM part_masters WHERE part_number = ?",
                (part_number,),
            )
            master_row = cursor.fetchone()
            if not master_row:
                raise ValueError(f"Part {part_number} does not exist.")

            latest_v = self._get_latest_part_version_row(conn, master_row["id"])
            if not latest_v:
                raise ValueError(f"No versions found for part {part_number}.")

            if latest_v["lifecycle_state"] != LifecycleState.IN_WORK.value:
                raise ValueError(
                    f"Part {part_number} is in state {latest_v['lifecycle_state']}. "
                    "Only IN_WORK parts can be iterated. Revise the part if it is RELEASED."
                )

            new_iteration = latest_v["iteration"] + 1
            new_v_id = str(uuid.uuid4())
            now_iso = datetime.utcnow().isoformat()

            cursor.execute(
                """
                INSERT INTO part_versions (
                    id, master_id, revision, iteration, lifecycle_state,
                    description, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'wcadmin', ?, ?)
                """,
                (
                    new_v_id,
                    master_row["id"],
                    latest_v["revision"],
                    new_iteration,
                    LifecycleState.IN_WORK.value,
                    description or latest_v["description"],
                    now_iso,
                    now_iso,
                ),
            )

            # Copy BOM links from prior iteration (standard Windchill persistence)
            cursor.execute(
                "SELECT * FROM bom_links WHERE parent_version_id = ?",
                (latest_v["id"],),
            )
            for bom in cursor.fetchall():
                cursor.execute(
                    """
                    INSERT INTO bom_links (
                        id, parent_version_id, child_master_id, quantity,
                        unit, find_number, ref_designators, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        new_v_id,
                        bom["child_master_id"],
                        bom["quantity"],
                        bom["unit"],
                        bom["find_number"],
                        bom["ref_designators"],
                        bom["notes"],
                    ),
                )

            # Copy Document links
            cursor.execute(
                "SELECT * FROM part_doc_links WHERE part_version_id = ?",
                (latest_v["id"],),
            )
            for doc_link in cursor.fetchall():
                cursor.execute(
                    """
                    INSERT INTO part_doc_links (id, part_version_id, doc_version_id, link_type)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        new_v_id,
                        doc_link["doc_version_id"],
                        doc_link["link_type"],
                    ),
                )

            conn.commit()

        return PartVersion(
            id=new_v_id,
            master_id=master_row["id"],
            part_number=part_number,
            name=master_row["name"],
            revision=latest_v["revision"],
            iteration=new_iteration,
            version_label=f"{latest_v['revision']}.{new_iteration}",
            lifecycle_state=LifecycleState.IN_WORK,
            description=description or latest_v["description"],
        )

    def revise_part(
        self, part_number: str, description: str = ""
    ) -> PartVersion:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM part_masters WHERE part_number = ?",
                (part_number,),
            )
            master_row = cursor.fetchone()
            if not master_row:
                raise ValueError(f"Part {part_number} does not exist.")

            latest_v = self._get_latest_part_version_row(conn, master_row["id"])
            if not latest_v:
                raise ValueError(f"No versions found for part {part_number}.")

            if latest_v["lifecycle_state"] != LifecycleState.RELEASED.value:
                raise ValueError(
                    f"Part {part_number} is in state {latest_v['lifecycle_state']}. "
                    "Only RELEASED parts can be revised."
                )

            new_revision = self._next_revision(latest_v["revision"])
            new_v_id = str(uuid.uuid4())
            now_iso = datetime.utcnow().isoformat()

            cursor.execute(
                """
                INSERT INTO part_versions (
                    id, master_id, revision, iteration, lifecycle_state,
                    description, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?, 'wcadmin', ?, ?)
                """,
                (
                    new_v_id,
                    master_row["id"],
                    new_revision,
                    LifecycleState.IN_WORK.value,
                    description or latest_v["description"],
                    now_iso,
                    now_iso,
                ),
            )

            # Copy BOM links from prior revision
            cursor.execute(
                "SELECT * FROM bom_links WHERE parent_version_id = ?",
                (latest_v["id"],),
            )
            for bom in cursor.fetchall():
                cursor.execute(
                    """
                    INSERT INTO bom_links (
                        id, parent_version_id, child_master_id, quantity,
                        unit, find_number, ref_designators, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        new_v_id,
                        bom["child_master_id"],
                        bom["quantity"],
                        bom["unit"],
                        bom["find_number"],
                        bom["ref_designators"],
                        bom["notes"],
                    ),
                )

            # Copy Doc links
            cursor.execute(
                "SELECT * FROM part_doc_links WHERE part_version_id = ?",
                (latest_v["id"],),
            )
            for doc_link in cursor.fetchall():
                cursor.execute(
                    """
                    INSERT INTO part_doc_links (id, part_version_id, doc_version_id, link_type)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        new_v_id,
                        doc_link["doc_version_id"],
                        doc_link["link_type"],
                    ),
                )

            conn.commit()

        return PartVersion(
            id=new_v_id,
            master_id=master_row["id"],
            part_number=part_number,
            name=master_row["name"],
            revision=new_revision,
            iteration=1,
            version_label=f"{new_revision}.1",
            lifecycle_state=LifecycleState.IN_WORK,
            description=description or latest_v["description"],
        )

    def set_part_lifecycle_state(
        self, part_number: str, target_state: LifecycleState
    ) -> PartVersion:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM part_masters WHERE part_number = ?",
                (part_number,),
            )
            master_row = cursor.fetchone()
            if not master_row:
                raise ValueError(f"Part {part_number} does not exist.")

            latest_v = self._get_latest_part_version_row(conn, master_row["id"])
            if not latest_v:
                raise ValueError(f"No versions found for part {part_number}.")

            current_state = LifecycleState(latest_v["lifecycle_state"])

            # Windchill lifecycle state machine validation
            valid_transitions = {
                LifecycleState.IN_WORK: [LifecycleState.UNDER_REVIEW],
                LifecycleState.UNDER_REVIEW: [
                    LifecycleState.RELEASED,
                    LifecycleState.IN_WORK,
                ],
                LifecycleState.RELEASED: [LifecycleState.OBSOLETE],
                LifecycleState.OBSOLETE: [],
            }

            if target_state not in valid_transitions[current_state]:
                raise ValueError(
                    f"Illegal lifecycle transition: Cannot transition {part_number} "
                    f"from {current_state.value} to {target_state.value}. "
                    f"Permitted next states: {[s.value for s in valid_transitions[current_state]]}"
                )

            now_iso = datetime.utcnow().isoformat()
            cursor.execute(
                """
                UPDATE part_versions
                SET lifecycle_state = ?, updated_at = ?
                WHERE id = ?
                """,
                (target_state.value, now_iso, latest_v["id"]),
            )
            conn.commit()

        return PartVersion(
            id=latest_v["id"],
            master_id=master_row["id"],
            part_number=part_number,
            name=master_row["name"],
            revision=latest_v["revision"],
            iteration=latest_v["iteration"],
            version_label=f"{latest_v['revision']}.{latest_v['iteration']}",
            lifecycle_state=target_state,
            description=latest_v["description"] or "",
            created_by=latest_v["created_by"],
            created_at=datetime.fromisoformat(latest_v["created_at"]),
            updated_at=datetime.fromisoformat(now_iso),
        )

    # -------------------------------------------------------------------------
    # Bill of Materials (BOM)
    # -------------------------------------------------------------------------

    def get_part_bom(
        self, part_number: str, levels: int = 1, version: str | None = None
    ) -> BOMNode | None:
        part_detail = self.get_part(part_number, version)
        if not part_detail:
            return None

        root = BOMNode(
            part_number=part_detail.master.part_number,
            name=part_detail.master.name,
            version_label=part_detail.version.version_label,
            lifecycle_state=part_detail.version.lifecycle_state.value,
            level=0,
        )

        with self._get_connection() as conn:
            self._explode_bom(conn, root, part_detail.version.id, current_level=1, max_level=levels)

        return root

    def _explode_bom(
        self,
        conn: sqlite3.Connection,
        parent_node: BOMNode,
        parent_version_id: str,
        current_level: int,
        max_level: int,
    ) -> None:
        if current_level > max_level:
            return

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT b.*, m.part_number as child_number, m.name as child_name, m.id as child_m_id
            FROM bom_links b
            JOIN part_masters m ON b.child_master_id = m.id
            WHERE b.parent_version_id = ?
            ORDER BY b.find_number ASC, m.part_number ASC
            """,
            (parent_version_id,),
        )
        links = cursor.fetchall()

        for link in links:
            # fetch child's latest version
            child_v = self._get_latest_part_version_row(conn, link["child_m_id"])
            v_label = f"{child_v['revision']}.{child_v['iteration']}" if child_v else "A.1"
            l_state = child_v["lifecycle_state"] if child_v else "IN_WORK"

            child_node = BOMNode(
                part_number=link["child_number"],
                name=link["child_name"],
                version_label=v_label,
                lifecycle_state=l_state,
                quantity=link["quantity"],
                unit=link["unit"],
                find_number=link["find_number"],
                ref_designators=link["ref_designators"],
                level=current_level,
            )
            parent_node.children.append(child_node)

            if child_v and current_level < max_level:
                self._explode_bom(
                    conn, child_node, child_v["id"], current_level + 1, max_level
                )

    def get_where_used(
        self, part_number: str, top_level_only: bool = False
    ) -> list[WhereUsedItem]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM part_masters WHERE part_number = ?",
                (part_number,),
            )
            child_m = cursor.fetchone()
            if not child_m:
                return []

            cursor.execute(
                """
                SELECT b.quantity, b.unit, b.find_number,
                       pm.part_number as parent_number, pm.name as parent_name,
                       pv.revision, pv.iteration, pv.lifecycle_state
                FROM bom_links b
                JOIN part_versions pv ON b.parent_version_id = pv.id
                JOIN part_masters pm ON pv.master_id = pm.id
                WHERE b.child_master_id = ?
                  AND pv.id = (
                      SELECT id FROM part_versions
                      WHERE master_id = pm.id
                      ORDER BY revision DESC, iteration DESC LIMIT 1
                  )
                ORDER BY pm.part_number ASC
                """,
                (child_m["id"],),
            )
            rows = cursor.fetchall()

            return [
                WhereUsedItem(
                    parent_part_number=r["parent_number"],
                    parent_name=r["parent_name"],
                    parent_version_label=f"{r['revision']}.{r['iteration']}",
                    parent_lifecycle_state=r["lifecycle_state"],
                    quantity=r["quantity"],
                    unit=r["unit"],
                    find_number=r["find_number"],
                )
                for r in rows
            ]

    def add_bom_component(
        self,
        parent_part_number: str,
        child_part_number: str,
        quantity: float = 1.0,
        unit: str = "ea",
        find_number: int | None = None,
        ref_designators: str | None = None,
        notes: str = "",
    ) -> BOMLink:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # check parent
            cursor.execute(
                "SELECT * FROM part_masters WHERE part_number = ?",
                (parent_part_number,),
            )
            p_master = cursor.fetchone()
            if not p_master:
                raise ValueError(f"Parent part {parent_part_number} does not exist.")

            p_v = self._get_latest_part_version_row(conn, p_master["id"])
            if not p_v:
                raise ValueError(f"No version for parent part {parent_part_number}.")

            if p_v["lifecycle_state"] != LifecycleState.IN_WORK.value:
                raise ValueError(
                    f"Parent part {parent_part_number} is in state {p_v['lifecycle_state']}. "
                    "Cannot modify BOM of a non-IN_WORK part. Revise or iterate it first."
                )

            # check child
            cursor.execute(
                "SELECT * FROM part_masters WHERE part_number = ?",
                (child_part_number,),
            )
            c_master = cursor.fetchone()
            if not c_master:
                raise ValueError(f"Child component {child_part_number} does not exist.")

            if p_master["id"] == c_master["id"]:
                raise ValueError("Cannot add a part as a BOM component of itself.")

            link_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO bom_links (
                    id, parent_version_id, child_master_id, quantity, unit,
                    find_number, ref_designators, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    link_id,
                    p_v["id"],
                    c_master["id"],
                    quantity,
                    unit,
                    find_number,
                    ref_designators,
                    notes,
                ),
            )
            conn.commit()

        return BOMLink(
            id=link_id,
            parent_version_id=p_v["id"],
            child_master_id=c_master["id"],
            child_part_number=child_part_number,
            child_name=c_master["name"],
            quantity=quantity,
            unit=unit,
            find_number=find_number,
            ref_designators=ref_designators,
            notes=notes,
        )

    def remove_bom_component(
        self, parent_part_number: str, child_part_number: str
    ) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM part_masters WHERE part_number = ?",
                (parent_part_number,),
            )
            p_master = cursor.fetchone()
            if not p_master:
                raise ValueError(f"Parent part {parent_part_number} does not exist.")

            p_v = self._get_latest_part_version_row(conn, p_master["id"])
            if not p_v:
                raise ValueError(f"No version found for {parent_part_number}.")

            if p_v["lifecycle_state"] != LifecycleState.IN_WORK.value:
                raise ValueError(
                    f"Parent part {parent_part_number} is in state {p_v['lifecycle_state']}. "
                    "Cannot remove BOM components from a non-IN_WORK part."
                )

            cursor.execute(
                "SELECT id FROM part_masters WHERE part_number = ?",
                (child_part_number,),
            )
            c_master = cursor.fetchone()
            if not c_master:
                raise ValueError(f"Child component {child_part_number} does not exist.")

            cursor.execute(
                """
                DELETE FROM bom_links
                WHERE parent_version_id = ? AND child_master_id = ?
                """,
                (p_v["id"], c_master["id"]),
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted

    # -------------------------------------------------------------------------
    # Document Management
    # -------------------------------------------------------------------------

    def get_document(
        self, doc_number: str, version: str | None = None
    ) -> DocumentVersion | None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM document_masters WHERE doc_number = ?",
                (doc_number,),
            )
            m_row = cursor.fetchone()
            if not m_row:
                return None

            if version:
                if "." in version:
                    rev, it_str = version.split(".", 1)
                    cursor.execute(
                        """
                        SELECT * FROM document_versions
                        WHERE master_id = ? AND revision = ? AND iteration = ?
                        """,
                        (m_row["id"], rev, int(it_str)),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT * FROM document_versions
                        WHERE master_id = ? AND revision = ?
                        ORDER BY iteration DESC LIMIT 1
                        """,
                        (m_row["id"], version),
                    )
            else:
                cursor.execute(
                    """
                    SELECT * FROM document_versions
                    WHERE master_id = ?
                    ORDER BY revision DESC, iteration DESC LIMIT 1
                    """,
                    (m_row["id"],),
                )
            v_row = cursor.fetchone()
            if not v_row:
                return None

            return DocumentVersion(
                id=v_row["id"],
                master_id=v_row["master_id"],
                doc_number=m_row["doc_number"],
                name=m_row["name"],
                doc_type=DocType(m_row["doc_type"]),
                revision=v_row["revision"],
                iteration=v_row["iteration"],
                version_label=f"{v_row['revision']}.{v_row['iteration']}",
                lifecycle_state=LifecycleState(v_row["lifecycle_state"]),
                file_name=v_row["file_name"],
                file_size_bytes=v_row["file_size_bytes"],
                mime_type=v_row["mime_type"],
                file_uri=v_row["file_uri"],
                created_by=v_row["created_by"],
                created_at=datetime.fromisoformat(v_row["created_at"]),
                updated_at=datetime.fromisoformat(v_row["updated_at"]),
            )

    def search_documents(
        self, query: str = "", doc_type: str | None = None, limit: int = 20
    ) -> list[DocumentVersion]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            q_pattern = f"%{query}%"

            sql = """
                SELECT m.doc_number, m.name, m.doc_type, v.*
                FROM document_masters m
                JOIN document_versions v ON m.id = v.master_id
                WHERE (m.doc_number LIKE ? OR m.name LIKE ?)
                  AND v.id = (
                      SELECT id FROM document_versions
                      WHERE master_id = m.id
                      ORDER BY revision DESC, iteration DESC LIMIT 1
                  )
            """
            params: list[Any] = [q_pattern, q_pattern]

            if doc_type:
                sql += " AND m.doc_type = ?"
                params.append(doc_type)

            sql += " ORDER BY m.doc_number ASC LIMIT ?"
            params.append(limit)

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            return [
                DocumentVersion(
                    id=r["id"],
                    master_id=r["master_id"],
                    doc_number=r["doc_number"],
                    name=r["name"],
                    doc_type=DocType(r["doc_type"]),
                    revision=r["revision"],
                    iteration=r["iteration"],
                    version_label=f"{r['revision']}.{r['iteration']}",
                    lifecycle_state=LifecycleState(r["lifecycle_state"]),
                    file_name=r["file_name"],
                    file_size_bytes=r["file_size_bytes"],
                    mime_type=r["mime_type"],
                    file_uri=r["file_uri"],
                    created_by=r["created_by"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
                for r in rows
            ]

    def create_document(
        self,
        doc_number: str,
        name: str,
        doc_type: DocType,
        file_name: str | None = None,
        file_size_bytes: int | None = None,
        mime_type: str | None = None,
    ) -> DocumentVersion:
        now_iso = datetime.utcnow().isoformat()
        m_id = str(uuid.uuid4())
        v_id = str(uuid.uuid4())
        file_uri = f"plm://vault/{doc_number}/{file_name}" if file_name else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO document_masters (id, doc_number, name, doc_type, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (m_id, doc_number, name, doc_type.value, now_iso),
            )
            cursor.execute(
                """
                INSERT INTO document_versions (
                    id, master_id, revision, iteration, lifecycle_state,
                    file_name, file_size_bytes, mime_type, file_uri,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, 'A', 1, ?, ?, ?, ?, ?, 'wcadmin', ?, ?)
                """,
                (
                    v_id,
                    m_id,
                    LifecycleState.IN_WORK.value,
                    file_name,
                    file_size_bytes,
                    mime_type,
                    file_uri,
                    now_iso,
                    now_iso,
                ),
            )
            conn.commit()

        return DocumentVersion(
            id=v_id,
            master_id=m_id,
            doc_number=doc_number,
            name=name,
            doc_type=doc_type,
            revision="A",
            iteration=1,
            version_label="A.1",
            lifecycle_state=LifecycleState.IN_WORK,
            file_name=file_name,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
            file_uri=file_uri,
        )

    def link_document_to_part(
        self,
        part_number: str,
        doc_number: str,
        link_type: PartDocLinkType = PartDocLinkType.DESCRIBES,
    ) -> PartDocLink:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # check part
            cursor.execute(
                "SELECT id FROM part_masters WHERE part_number = ?",
                (part_number,),
            )
            pm = cursor.fetchone()
            if not pm:
                raise ValueError(f"Part {part_number} does not exist.")
            pv = self._get_latest_part_version_row(conn, pm["id"])
            if not pv:
                raise ValueError(f"No version for part {part_number}.")

            # check doc
            cursor.execute(
                "SELECT * FROM document_masters WHERE doc_number = ?",
                (doc_number,),
            )
            dm = cursor.fetchone()
            if not dm:
                raise ValueError(f"Document {doc_number} does not exist.")

            cursor.execute(
                """
                SELECT * FROM document_versions
                WHERE master_id = ?
                ORDER BY revision DESC, iteration DESC LIMIT 1
                """,
                (dm["id"],),
            )
            dv = cursor.fetchone()
            if not dv:
                raise ValueError(f"No version for document {doc_number}.")

            link_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO part_doc_links (id, part_version_id, doc_version_id, link_type)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(part_version_id, doc_version_id, link_type) DO NOTHING
                """,
                (link_id, pv["id"], dv["id"], link_type.value),
            )
            conn.commit()

        return PartDocLink(
            id=link_id,
            part_version_id=pv["id"],
            doc_version_id=dv["id"],
            part_number=part_number,
            doc_number=doc_number,
            doc_name=dm["name"],
            doc_version_label=f"{dv['revision']}.{dv['iteration']}",
            link_type=link_type,
        )

    # -------------------------------------------------------------------------
    # Change Management (ECR & ECN)
    # -------------------------------------------------------------------------

    def create_change_request(
        self,
        title: str,
        description: str,
        category: ChangeCategory,
        priority: ChangePriority,
        affected_parts: list[str],
    ) -> ChangeRequest:
        now_iso = datetime.utcnow().isoformat()
        cr_id = str(uuid.uuid4())

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM change_requests")
            next_num = cursor.fetchone()["count"] + 1
            cr_number = f"CR-{next_num:04d}"

            cursor.execute(
                """
                INSERT INTO change_requests (
                    id, cr_number, title, description, category, priority,
                    state, affected_parts, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cr_id,
                    cr_number,
                    title,
                    description,
                    category.value,
                    priority.value,
                    ChangeRequestState.OPEN.value,
                    json.dumps(affected_parts),
                    now_iso,
                    now_iso,
                ),
            )
            conn.commit()

        return ChangeRequest(
            id=cr_id,
            cr_number=cr_number,
            title=title,
            description=description,
            category=category,
            priority=priority,
            state=ChangeRequestState.OPEN,
            affected_part_numbers=affected_parts,
        )

    def get_change_request(self, cr_number: str) -> ChangeRequest | None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM change_requests WHERE cr_number = ?",
                (cr_number,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return ChangeRequest(
                id=row["id"],
                cr_number=row["cr_number"],
                title=row["title"],
                description=row["description"],
                category=ChangeCategory(row["category"]),
                priority=ChangePriority(row["priority"]),
                state=ChangeRequestState(row["state"]),
                affected_part_numbers=json.loads(row["affected_parts"] or "[]"),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )

    def create_change_notice(
        self,
        title: str,
        description: str,
        cr_number: str | None = None,
    ) -> ChangeNotice:
        now_iso = datetime.utcnow().isoformat()
        cn_id = str(uuid.uuid4())
        cr_id = None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            if cr_number:
                cursor.execute(
                    "SELECT id FROM change_requests WHERE cr_number = ?",
                    (cr_number,),
                )
                cr_row = cursor.fetchone()
                if cr_row:
                    cr_id = cr_row["id"]
                    # Move CR to APPROVED/IN_WORK
                    cursor.execute(
                        "UPDATE change_requests SET state = ? WHERE id = ?",
                        (ChangeRequestState.APPROVED.value, cr_id),
                    )

            cursor.execute("SELECT COUNT(*) as count FROM change_notices")
            next_num = cursor.fetchone()["count"] + 1
            cn_number = f"CN-{next_num:04d}"

            cursor.execute(
                """
                INSERT INTO change_notices (
                    id, cn_number, change_request_id, title, description,
                    state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cn_id,
                    cn_number,
                    cr_id,
                    title,
                    description,
                    ChangeNoticeState.OPEN.value,
                    now_iso,
                    now_iso,
                ),
            )
            conn.commit()

        return ChangeNotice(
            id=cn_id,
            cn_number=cn_number,
            change_request_id=cr_id,
            cr_number=cr_number,
            title=title,
            description=description,
            state=ChangeNoticeState.OPEN,
        )

    def get_change_notice(self, cn_number: str) -> ChangeNotice | None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT cn.*, cr.cr_number
                FROM change_notices cn
                LEFT JOIN change_requests cr ON cn.change_request_id = cr.id
                WHERE cn.cn_number = ?
                """,
                (cn_number,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            cursor.execute(
                "SELECT * FROM change_affected_items WHERE change_notice_id = ?",
                (row["id"],),
            )
            aff_rows = cursor.fetchall()
            affected = [
                ChangeAffectedItem(
                    id=ar["id"],
                    change_notice_id=ar["change_notice_id"],
                    item_type=ar["item_type"],
                    item_number=ar["item_number"],
                    version_label=ar["version_label"],
                    disposition=ItemDisposition(ar["disposition"]),
                )
                for ar in aff_rows
            ]

            cursor.execute(
                "SELECT * FROM change_resulting_items WHERE change_notice_id = ?",
                (row["id"],),
            )
            res_rows = cursor.fetchall()
            resulting = [
                ChangeResultingItem(
                    id=rr["id"],
                    change_notice_id=rr["change_notice_id"],
                    item_type=rr["item_type"],
                    item_number=rr["item_number"],
                    target_version_label=rr["target_version_label"],
                    target_state=LifecycleState(rr["target_state"]),
                )
                for rr in res_rows
            ]

            return ChangeNotice(
                id=row["id"],
                cn_number=row["cn_number"],
                change_request_id=row["change_request_id"],
                cr_number=row["cr_number"],
                title=row["title"],
                description=row["description"],
                state=ChangeNoticeState(row["state"]),
                affected_items=affected,
                resulting_items=resulting,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )

    def add_change_affected_item(
        self,
        cn_number: str,
        item_type: str,
        item_number: str,
        disposition: ItemDisposition,
    ) -> ChangeAffectedItem:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM change_notices WHERE cn_number = ?",
                (cn_number,),
            )
            cn_row = cursor.fetchone()
            if not cn_row:
                raise ValueError(f"Change notice {cn_number} does not exist.")

            # Look up version label
            version_label = "A.1"
            if item_type.upper() == "PART":
                p = self.get_part(item_number)
                if p:
                    version_label = p.version.version_label
            elif item_type.upper() == "DOCUMENT":
                d = self.get_document(item_number)
                if d:
                    version_label = d.version_label

            aff_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO change_affected_items (
                    id, change_notice_id, item_type, item_number,
                    version_label, disposition
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    aff_id,
                    cn_row["id"],
                    item_type.upper(),
                    item_number,
                    version_label,
                    disposition.value,
                ),
            )
            conn.commit()

        return ChangeAffectedItem(
            id=aff_id,
            change_notice_id=cn_row["id"],
            item_type=item_type.upper(),
            item_number=item_number,
            version_label=version_label,
            disposition=disposition,
        )

    def execute_change_notice(self, cn_number: str) -> ChangeNotice:
        cn = self.get_change_notice(cn_number)
        if not cn:
            raise ValueError(f"Change notice {cn_number} does not exist.")

        if cn.state in (ChangeNoticeState.COMPLETED, ChangeNoticeState.CANCELLED):
            raise ValueError(f"Change notice {cn_number} is already {cn.state.value}.")

        now_iso = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Process affected items
            for item in cn.affected_items:
                if item.item_type == "PART":
                    # If disposition is SCRAP or REWORK, mark obsolete or update state
                    if item.disposition == ItemDisposition.SCRAP:
                        cursor.execute(
                            """
                            UPDATE part_versions
                            SET lifecycle_state = ?, updated_at = ?
                            WHERE master_id = (SELECT id FROM part_masters WHERE part_number = ?)
                            """,
                            (LifecycleState.OBSOLETE.value, now_iso, item.item_number),
                        )

            # Mark change notice as COMPLETED
            cursor.execute(
                """
                UPDATE change_notices
                SET state = ?, updated_at = ?
                WHERE id = ?
                """,
                (ChangeNoticeState.COMPLETED.value, now_iso, cn.id),
            )

            # If linked to a CR, resolve it
            if cn.change_request_id:
                cursor.execute(
                    """
                    UPDATE change_requests
                    SET state = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (ChangeRequestState.RESOLVED.value, now_iso, cn.change_request_id),
                )

            conn.commit()

        updated_cn = self.get_change_notice(cn_number)
        assert updated_cn is not None
        return updated_cn

    # -------------------------------------------------------------------------
    # Supplier & Sourcing Management (AML/AVL)
    # -------------------------------------------------------------------------

    def search_manufacturers(
        self, query: str = "", status: str | None = None
    ) -> list[Manufacturer]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            q_pattern = f"%{query}%"

            sql = "SELECT * FROM manufacturers WHERE (name LIKE ? OR cage_code LIKE ?)"
            params: list[Any] = [q_pattern, q_pattern]

            if status:
                sql += " AND status = ?"
                params.append(status)

            sql += " ORDER BY name ASC"
            cursor.execute(sql, params)
            rows = cursor.fetchall()

            return [
                Manufacturer(
                    id=r["id"],
                    name=r["name"],
                    cage_code=r["cage_code"],
                    status=ManufacturerStatus(r["status"]),
                    country=r["country"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
                for r in rows
            ]

    def add_manufacturer(
        self, name: str, cage_code: str | None = None, country: str = "USA"
    ) -> Manufacturer:
        now_iso = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM manufacturers WHERE name = ?", (name,))
            existing = cursor.fetchone()
            if existing:
                m_id = existing["id"]
                if cage_code:
                    cursor.execute(
                        "UPDATE manufacturers SET cage_code = ? WHERE id = ?",
                        (cage_code, m_id),
                    )
            else:
                m_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO manufacturers (id, name, cage_code, status, country, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        m_id,
                        name,
                        cage_code,
                        ManufacturerStatus.ACTIVE.value,
                        country,
                        now_iso,
                    ),
                )
            conn.commit()

        return Manufacturer(
            id=m_id,
            name=name,
            cage_code=cage_code,
            status=ManufacturerStatus.ACTIVE,
            country=country,
        )

    def add_manufacturer_part(
        self, mfr_name: str, mfr_part_number: str, description: str = ""
    ) -> ManufacturerPart:
        now_iso = datetime.utcnow().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM manufacturers WHERE name = ?", (mfr_name,)
            )
            m_row = cursor.fetchone()
            if not m_row:
                mfr = self.add_manufacturer(mfr_name)
                mfr_id = mfr.id
            else:
                mfr_id = m_row["id"]

            cursor.execute(
                "SELECT id FROM manufacturer_parts WHERE manufacturer_id = ? AND mfr_part_number = ?",
                (mfr_id, mfr_part_number),
            )
            existing_mp = cursor.fetchone()
            if existing_mp:
                mp_id = existing_mp["id"]
                if description:
                    cursor.execute(
                        "UPDATE manufacturer_parts SET description = ? WHERE id = ?",
                        (description, mp_id),
                    )
            else:
                mp_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO manufacturer_parts (id, manufacturer_id, mfr_part_number, description, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (mp_id, mfr_id, mfr_part_number, description, now_iso),
                )
            conn.commit()

        return ManufacturerPart(
            id=mp_id,
            manufacturer_id=mfr_id,
            manufacturer_name=mfr_name,
            mfr_part_number=mfr_part_number,
            description=description,
        )

    def set_sourcing_link(
        self,
        part_number: str,
        mfr_name: str,
        mfr_part_number: str,
        status: SourcingStatus,
        preference_rank: int = 1,
    ) -> AMLLink:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM part_masters WHERE part_number = ?",
                (part_number,),
            )
            pm = cursor.fetchone()
            if not pm:
                raise ValueError(f"Part {part_number} does not exist.")

            mp = self.add_manufacturer_part(mfr_name, mfr_part_number)

            link_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO aml_links (
                    id, part_master_id, mfr_part_id, sourcing_status, preference_rank
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(part_master_id, mfr_part_id) DO UPDATE SET
                    sourcing_status=excluded.sourcing_status,
                    preference_rank=excluded.preference_rank
                """,
                (link_id, pm["id"], mp.id, status.value, preference_rank),
            )
            conn.commit()

        return AMLLink(
            id=link_id,
            part_master_id=pm["id"],
            internal_part_number=part_number,
            mfr_part_id=mp.id,
            mfr_name=mfr_name,
            mfr_part_number=mfr_part_number,
            sourcing_status=status,
            preference_rank=preference_rank,
        )

    def get_part_aml(self, part_number: str) -> list[AMLLink]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM part_masters WHERE part_number = ?",
                (part_number,),
            )
            pm = cursor.fetchone()
            if not pm:
                return []

            cursor.execute(
                """
                SELECT a.*, mp.mfr_part_number, m.name as mfr_name
                FROM aml_links a
                JOIN manufacturer_parts mp ON a.mfr_part_id = mp.id
                JOIN manufacturers m ON mp.manufacturer_id = m.id
                WHERE a.part_master_id = ?
                ORDER BY a.preference_rank ASC
                """,
                (pm["id"],),
            )
            rows = cursor.fetchall()

            return [
                AMLLink(
                    id=r["id"],
                    part_master_id=pm["id"],
                    internal_part_number=part_number,
                    mfr_part_id=r["mfr_part_id"],
                    mfr_name=r["mfr_name"],
                    mfr_part_number=r["mfr_part_number"],
                    sourcing_status=SourcingStatus(r["sourcing_status"]),
                    preference_rank=r["preference_rank"],
                )
                for r in rows
            ]
