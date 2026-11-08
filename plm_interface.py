"""PLM Interface Definition.

Defines the core normalized Pydantic data models and the abstract PLMBackend
interface for interacting with Product Lifecycle Management (PLM) backends
(e.g., SQLite MockBackend, PTC Windchill REST/OData).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


# =============================================================================
# Domain Enums
# =============================================================================

class LifecycleState(str, Enum):
    """Windchill-style lifecycle states."""
    IN_WORK = "IN_WORK"
    UNDER_REVIEW = "UNDER_REVIEW"
    RELEASED = "RELEASED"
    OBSOLETE = "OBSOLETE"


class DocType(str, Enum):
    """Document classification types."""
    SPECIFICATION = "SPECIFICATION"
    CAD_DRAWING = "CAD_DRAWING"
    TEST_REPORT = "TEST_REPORT"
    USER_MANUAL = "USER_MANUAL"


class ChangeCategory(str, Enum):
    """Category classification for Change Requests."""
    DESIGN_IMPROVEMENT = "DESIGN_IMPROVEMENT"
    DEFECT = "DEFECT"
    COST_REDUCTION = "COST_REDUCTION"
    COMPLIANCE = "COMPLIANCE"


class ChangePriority(str, Enum):
    """Priority levels for change management."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EMERGENCY = "EMERGENCY"


class SourcingStatus(str, Enum):
    """AML/AVL sourcing status for suppliers."""
    PREFERRED = "PREFERRED"
    APPROVED = "APPROVED"
    DO_NOT_USE = "DO_NOT_USE"
    UNDER_REVIEW = "UNDER_REVIEW"


# =============================================================================
# Core Domain Pydantic Models
# =============================================================================

class Part(BaseModel):
    """Represents a PLM Part item following Windchill Master / Version semantics.

    Attributes:
        part_number: Unique part number (e.g. 'DRN-1000').
        name: Human-readable component or assembly title.
        revision: Major revision identifier (e.g. 'A', 'B').
        iteration: Minor iteration sequence number (e.g. 1, 2).
        version_label: Combined revision and iteration string (e.g. 'A.1').
        lifecycle_state: Current state in the lifecycle state machine.
        description: Functional description or engineering specifications.
        created_at: Timestamp when the item was first registered.
        updated_at: Timestamp of the latest modification.
    """
    part_number: str
    name: str
    revision: str = "A"
    iteration: int = 1
    version_label: str = "A.1"
    lifecycle_state: LifecycleState = LifecycleState.IN_WORK
    description: str = ""
    make_buy: str = "MAKE"
    material: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BomLink(BaseModel):
    """Represents an association usage link between a parent assembly and child part.

    Equivalent to PTC Windchill WTPartUsageLink.

    Attributes:
        parent_part_number: Part number of the parent assembly.
        child_part_number: Part number of the consumed child component.
        child_name: Name of the child part.
        quantity: Usage quantity per parent assembly.
        unit: Unit of measure (e.g. 'ea', 'mm', 'g').
        find_number: Assembly line or balloon sequence number (e.g. 10, 20).
        ref_designators: Circuit or mechanical reference designators (e.g. 'C1, R2').
        level: Hierarchy depth in multi-level BOM explosion (1 = direct child).
        notes: Engineering usage notes.
    """
    parent_part_number: str
    child_part_number: str
    child_name: str = ""
    quantity: float = 1.0
    unit: str = "ea"
    find_number: int | None = None
    ref_designators: str | None = None
    level: int = 1
    bom_type: str = "EBOM"
    notes: str = ""


class Document(BaseModel):
    """Represents an engineering document or CAD file in the PLM vault.

    Equivalent to PTC Windchill WTDocument.

    Attributes:
        doc_number: Unique document number (e.g. 'DOC-SPEC-1000').
        name: Title of the document.
        doc_type: Classification type (SPECIFICATION, CAD_DRAWING, etc.).
        revision: Document revision letter.
        iteration: Document iteration sequence number.
        version_label: Formatted revision and iteration (e.g. 'A.1').
        lifecycle_state: Lifecycle state of the document version.
        file_name: Name of the primary file attachment.
        file_size_bytes: Size of the attachment in bytes.
        mime_type: MIME media type of the attachment.
        linked_parts: Part numbers linked to this document (Describes/References).
        created_at: Creation timestamp.
    """
    doc_number: str
    name: str
    doc_type: DocType = DocType.SPECIFICATION
    revision: str = "A"
    iteration: int = 1
    version_label: str = "A.1"
    lifecycle_state: LifecycleState = LifecycleState.IN_WORK
    file_name: str | None = None
    file_size_bytes: int | None = None
    mime_type: str | None = None
    linked_parts: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChangeRequest(BaseModel):
    """Represents an Engineering Change Request (ECR).

    Equivalent to PTC Windchill WTChangeRequest2.

    Attributes:
        cr_number: Unique change request identifier (e.g. 'CR-0001').
        title: Short title summarizing the change proposal.
        reason: Detailed justification, failure root cause, or requirement driver.
        category: Change category classification (DESIGN_IMPROVEMENT, DEFECT, etc.).
        priority: Urgency ranking (LOW, MEDIUM, HIGH, EMERGENCY).
        status: Lifecycle state (OPEN, UNDER_REVIEW, APPROVED, REJECTED, RESOLVED).
        affected_parts: List of part numbers impacted by this proposed change.
        created_at: Timestamp when the request was drafted/submitted.
    """
    cr_number: str
    title: str
    reason: str
    category: ChangeCategory = ChangeCategory.DESIGN_IMPROVEMENT
    priority: ChangePriority = ChangePriority.MEDIUM
    status: str = "OPEN"
    affected_parts: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Supplier(BaseModel):
    """Represents an external manufacturing vendor and Approved Manufacturer List (AML) partner.

    Attributes:
        name: Registered vendor/manufacturer organization name.
        cage_code: Commercial and Government Entity code (e.g. '7TM01').
        status: Operational status ('ACTIVE', 'INACTIVE', 'RESTRICTED').
        country: Country of headquarters/incorporation.
        manufacturer_parts: External catalog part numbers provided by this supplier.
        sourcing_status: Default sourcing approval status.
    """
    name: str
    cage_code: str | None = None
    status: str = "ACTIVE"
    country: str = "USA"
    manufacturer_parts: list[str] = Field(default_factory=list)
    sourcing_status: SourcingStatus = SourcingStatus.APPROVED


# =============================================================================
# Analytics & Audit Result Models
# =============================================================================

class BomComparisonItem(BaseModel):
    """Delta item between two BOM assemblies."""
    part_number: str
    name: str
    change_type: str  # "ADDED", "REMOVED", "QUANTITY_CHANGED", "UNCHANGED"
    quantity_a: float | None = None
    quantity_b: float | None = None
    unit: str = "ea"
    find_number_a: int | None = None
    find_number_b: int | None = None


class BomComparisonResult(BaseModel):
    """Result of comparing two assembly BOMs (e.g., across revisions or configurations)."""
    assembly_a: str
    assembly_b: str
    differences: list[BomComparisonItem] = Field(default_factory=list)
    added_parts: list[str] = Field(default_factory=list)
    removed_parts: list[str] = Field(default_factory=list)
    modified_parts: list[str] = Field(default_factory=list)


class DuplicateGroup(BaseModel):
    """Group of parts sharing potential duplicate characteristics."""
    match_criteria: str
    match_value: str
    parts: list[Part] = Field(default_factory=list)


class ObsoleteUsageItem(BaseModel):
    """Compliance audit violation: an obsolete component consumed inside a released assembly."""
    parent_part_number: str
    parent_name: str
    parent_version: str
    parent_lifecycle_state: str
    obsolete_child_part_number: str
    obsolete_child_name: str
    obsolete_child_version: str
    obsolete_child_state: str
    quantity: float
    unit: str


class ChangeImpactAnalysis(BaseModel):
    """Blast-radius analysis of proposed changes to a part."""
    target_part_number: str
    target_part_name: str
    target_lifecycle_state: str
    direct_parents: list[str] = Field(default_factory=list)
    all_affected_assemblies: list[str] = Field(default_factory=list)
    associated_documents: list[str] = Field(default_factory=list)
    active_change_requests: list[str] = Field(default_factory=list)
    approved_suppliers: list[str] = Field(default_factory=list)
    impact_level: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL


# =============================================================================
# Abstract PLMBackend Interface
# =============================================================================

class PLMBackend(ABC):
    """Abstract interface defining standard PLM operations and analytics.

    All MCP tools and API layers must interact strictly with this interface.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Automatically instrument all backend implementation methods with OpenTelemetry."""
        super().__init_subclass__(**kwargs)
        try:
            from telemetry import instrument_all_backend_methods
            instrument_all_backend_methods(cls)
        except Exception as e:
            import sys
            print(f"[Observability Warning] Failed to instrument {cls.__name__}: {e}", file=sys.stderr)

    @abstractmethod
    def search_parts(
        self,
        query: str = "",
        lifecycle_state: str | None = None,
        limit: int = 20,
        skip: int = 0,
    ) -> list[Part]:
        """Search parts by part number, name, or description with optional state filter.

        Args:
            query: Substring to match against part number, name, or description.
            lifecycle_state: Optional lifecycle state filter ('IN_WORK', 'UNDER_REVIEW', 'RELEASED', 'OBSOLETE').
            limit: Maximum number of search results to return (default 20).
            skip: Number of records to skip for pagination (default 0).

        Returns:
            List of Part records matching the criteria, resolving to their latest version.
        """
        pass

    @abstractmethod
    def get_parts_count(
        self,
        query: str = "",
        lifecycle_state: str | None = None,
    ) -> int:
        """Count parts matching search query and lifecycle state filter.

        Args:
            query: Substring to match against part number, name, or description.
            lifecycle_state: Optional lifecycle state filter.

        Returns:
            Total matching part count.
        """
        pass

    @abstractmethod
    def get_part(
        self, part_number: str, version: str | None = None
    ) -> Part | None:
        """Retrieve part details for a specific or latest version.

        Args:
            part_number: The unique part identification number (e.g. 'DRN-1000').
            version: Optional version label (e.g. 'A.1' or 'B.1'). If omitted, retrieves the latest iteration.

        Returns:
            Part object with version and lifecycle information, or None if not found.
        """
        pass

    @abstractmethod
    def get_bom(
        self, part_number: str, levels: int = 1
    ) -> list[BomLink]:
        """Retrieve single-level or multi-level indented Bill of Materials (BOM) usage links.

        Recursively explodes the assembly structure up to the requested depth.

        Args:
            part_number: The parent assembly part number.
            levels: Depth of BOM hierarchy explosion (1 for single-level, >1 for multi-level).

        Returns:
            List of BomLink records describing the hierarchy, components, and quantities.
        """
        pass

    @abstractmethod
    def where_used(
        self, part_number: str, recursive: bool = False
    ) -> list[dict[str, Any]]:
        """Perform where-used analysis to find assemblies that consume this part.

        Args:
            part_number: The component part number to look up.
            recursive: If False, returns direct parent assemblies.
                       If True, traverses recursively up to top-level assemblies.

        Returns:
            List of parent assembly records including part numbers, names, versions, and quantities.
        """
        pass

    @abstractmethod
    def compare_boms(self, a: str, b: str) -> BomComparisonResult:
        """Compare the Bill of Materials of two assemblies or two revisions of an assembly.

        Identifies components added, removed, or with modified quantities/attributes.

        Args:
            a: Part number (and optional version) of assembly A (e.g. 'DRN-1000' or 'DRN-1000:A.1').
            b: Part number (and optional version) of assembly B (e.g. 'DRN-1000' or 'DRN-1000:B.1').

        Returns:
            BomComparisonResult detailing added, removed, and quantity-modified parts.
        """
        pass

    @abstractmethod
    def find_duplicates(self) -> list[DuplicateGroup]:
        """Scan part catalog to detect duplicate or near-duplicate component definitions.

        Helps prevent part proliferation by identifying parts sharing identical names,
        descriptions, or specifications across the catalog.

        Returns:
            List of DuplicateGroup objects grouping potential redundant parts.
        """
        pass

    @abstractmethod
    def find_obsolete_in_released(self) -> list[ObsoleteUsageItem]:
        """Audit released product structures to detect obsolete components.

        Compliance and quality check: A RELEASED parent assembly should never
        reference a child component that has transitioned to OBSOLETE.

        Returns:
            List of ObsoleteUsageItem records detailing each compliance violation.
        """
        pass

    @abstractmethod
    def analyze_change_impact(self, part_number: str) -> ChangeImpactAnalysis:
        """Evaluate the blast radius and system impact of changing or obsoleting a part.

        Analyzes:
        1. Recursive where-used parent assemblies impacted.
        2. Associated engineering documents and CAD drawings requiring revision.
        3. Active change requests and notices already affecting this part.
        4. Approved suppliers and AML sourcing links requiring requalification.
        5. Computes overall impact severity rating (LOW, MEDIUM, HIGH, CRITICAL).

        Args:
            part_number: Part number being analyzed.

        Returns:
            ChangeImpactAnalysis containing all cross-functional impact data.
        """
        pass

    @abstractmethod
    def draft_change_request(
        self, title: str, affected_parts: list[str], reason: str
    ) -> ChangeRequest:
        """Generate a draft Engineering Change Request (ECR) for proposed alterations.

        Initializes the request in OPEN state, validates that all affected parts exist,
        and assigns a standard tracking identifier (e.g. 'CR-XXXX').

        Args:
            title: Short descriptive title of the change proposal.
            affected_parts: List of part numbers to link to this change request.
            reason: Justification or root cause problem description.

        Returns:
            ChangeRequest model instance.
        """
        pass

    @abstractmethod
    def get_change_requests(
        self, status: str | None = None, limit: int = 50, skip: int = 0
    ) -> list[ChangeRequest]:
        """Retrieve paginated change requests with optional state filter.

        Args:
            status: Optional lifecycle state filter ('OPEN', 'UNDER_REVIEW', 'APPROVED', etc.).
            limit: Maximum records to return.
            skip: Offset records to skip.

        Returns:
            List of ChangeRequest items.
        """
        pass

    @abstractmethod
    def get_change_requests_count(self, status: str | None = None) -> int:
        """Count total change requests matching optional state filter.

        Args:
            status: Optional lifecycle state filter.

        Returns:
            Total count of matching change requests.
        """
        pass

    @abstractmethod
    def find_unassigned_buy_parts(self) -> list[Part]:
        """Detect BUY parts with no registered AML suppliers.

        Returns:
            List of Part objects lacking approved suppliers.
        """
        pass

    @abstractmethod
    def find_ebom_mbom_mismatches(self) -> list[dict[str, Any]]:
        """Detect discrepancies between EBOM and MBOM product structures.

        Returns:
            List of dictionary discrepancy records.
        """
        pass

    @abstractmethod
    def find_rohs_risks(self) -> list[dict[str, Any]]:
        """Detect parts containing RoHS hazardous non-compliant materials.

        Returns:
            List of dictionary hazard records.
        """
        pass

