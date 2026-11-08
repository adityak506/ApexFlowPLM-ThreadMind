"""Mock QMS Backend Implementation.

Implements the QMSBackend interface using SQLite to manage non-conformance
reports (NCR), quality investigations, and field defect tickets.
"""

import json
import sqlite3
from pathlib import Path
from qms_interface import (
    DefectSeverity,
    DefectStatus,
    QMSBackend,
    QMSDefectReport,
)


class MockQMSBackend(QMSBackend):
    """SQLite-backed mock Quality Management System."""

    def __init__(self, db_path: str = "plm_mock.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensure QMS tables exist in the target database."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='qms_defect_reports'")
        if not cursor.fetchone():
            schema_path = Path(__file__).parent / "schema.sql"
            if schema_path.exists():
                with open(schema_path, "r", encoding="utf-8") as f:
                    ddl = f.read()
                self._conn.executescript(ddl)
                self._conn.commit()

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()

    def get_defects(
        self,
        part_number: str | None = None,
        severity: str | None = None,
        status: str | None = None,
    ) -> list[QMSDefectReport]:
        """Query non-conformance and defect records filtered by part, severity, or lifecycle status."""
        query = """
            SELECT defect_number, part_number, title, description, severity,
                   status, failure_mode, root_cause, linked_serial_numbers,
                   reported_by, containment_action, created_at, updated_at
            FROM qms_defect_reports
            WHERE 1=1
        """
        params: list[str] = []

        if part_number:
            query += " AND part_number = ?"
            params.append(part_number)
        if severity:
            query += " AND severity = ?"
            params.append(severity.upper())
        if status:
            query += " AND status = ?"
            params.append(status.upper())

        query += " ORDER BY created_at DESC"

        cursor = self._conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        reports: list[QMSDefectReport] = []
        for row in rows:
            serials_raw = row["linked_serial_numbers"] or "[]"
            try:
                serials = json.loads(serials_raw)
            except Exception:
                serials = []

            reports.append(
                QMSDefectReport(
                    defect_number=row["defect_number"],
                    part_number=row["part_number"],
                    title=row["title"],
                    description=row["description"],
                    severity=DefectSeverity(row["severity"]),
                    status=DefectStatus(row["status"]),
                    failure_mode=row["failure_mode"],
                    root_cause=row["root_cause"] or "",
                    linked_serial_numbers=serials,
                    reported_by=row["reported_by"],
                    containment_action=row["containment_action"] or "",
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
        return reports

    def get_defect_by_id(self, defect_number: str) -> QMSDefectReport | None:
        """Retrieve full details for a specific defect report by its unique tracking identifier."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT defect_number, part_number, title, description, severity,
                   status, failure_mode, root_cause, linked_serial_numbers,
                   reported_by, containment_action, created_at, updated_at
            FROM qms_defect_reports
            WHERE defect_number = ?
            """,
            (defect_number,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        serials_raw = row["linked_serial_numbers"] or "[]"
        try:
            serials = json.loads(serials_raw)
        except Exception:
            serials = []

        return QMSDefectReport(
            defect_number=row["defect_number"],
            part_number=row["part_number"],
            title=row["title"],
            description=row["description"],
            severity=DefectSeverity(row["severity"]),
            status=DefectStatus(row["status"]),
            failure_mode=row["failure_mode"],
            root_cause=row["root_cause"] or "",
            linked_serial_numbers=serials,
            reported_by=row["reported_by"],
            containment_action=row["containment_action"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
