"""Abstract PLMBackend interface. All MCP tools interact strictly with this interface."""

from abc import ABC, abstractmethod
from plm_mcp.models import (
    AMLLink,
    BOMLink,
    BOMNode,
    ChangeAffectedItem,
    ChangeCategory,
    ChangeNotice,
    ChangePriority,
    ChangeRequest,
    DocumentVersion,
    DocType,
    ItemDisposition,
    LifecycleState,
    Manufacturer,
    ManufacturerPart,
    PartDetail,
    PartDocLink,
    PartDocLinkType,
    PartSummary,
    PartVersion,
    SourcingStatus,
    WhereUsedItem,
)


class PLMBackend(ABC):
    """Abstract interface defining all standard PLM operations."""

    # -------------------------------------------------------------------------
    # Part Management
    # -------------------------------------------------------------------------

    @abstractmethod
    def get_part(
        self, part_number: str, version: str | None = None
    ) -> PartDetail | None:
        """Retrieve part details for latest or specified version (e.g. A.1)."""
        pass

    @abstractmethod
    def search_parts(
        self,
        query: str = "",
        lifecycle_state: str | None = None,
        limit: int = 20,
    ) -> list[PartSummary]:
        """Search parts by number, name, or description."""
        pass

    @abstractmethod
    def create_part(
        self, part_number: str, name: str, description: str = ""
    ) -> PartVersion:
        """Create a new part master and initial version A.1 in IN_WORK state."""
        pass

    @abstractmethod
    def revise_part(
        self, part_number: str, description: str = ""
    ) -> PartVersion:
        """Create a new revision (e.g., A.2 -> B.1) in IN_WORK from a RELEASED part."""
        pass

    @abstractmethod
    def iterate_part(
        self, part_number: str, description: str = ""
    ) -> PartVersion:
        """Increment iteration (e.g., A.1 -> A.2) for an IN_WORK part."""
        pass

    @abstractmethod
    def set_part_lifecycle_state(
        self, part_number: str, target_state: LifecycleState
    ) -> PartVersion:
        """Transition part lifecycle state following Windchill state machine."""
        pass

    # -------------------------------------------------------------------------
    # Bill of Materials (BOM) & Product Structure
    # -------------------------------------------------------------------------

    @abstractmethod
    def get_part_bom(
        self, part_number: str, levels: int = 1, version: str | None = None
    ) -> BOMNode | None:
        """Retrieve single-level or multi-level indented BOM tree for a part."""
        pass

    @abstractmethod
    def get_where_used(
        self, part_number: str, top_level_only: bool = False
    ) -> list[WhereUsedItem]:
        """Find parent assemblies consuming this part in their BOM."""
        pass

    @abstractmethod
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
        """Add a child component usage link to an IN_WORK parent assembly."""
        pass

    @abstractmethod
    def remove_bom_component(
        self, parent_part_number: str, child_part_number: str
    ) -> bool:
        """Remove a child component usage link from an IN_WORK parent assembly."""
        pass

    # -------------------------------------------------------------------------
    # Document Management
    # -------------------------------------------------------------------------

    @abstractmethod
    def get_document(
        self, doc_number: str, version: str | None = None
    ) -> DocumentVersion | None:
        """Retrieve document metadata for latest or specified version."""
        pass

    @abstractmethod
    def search_documents(
        self, query: str = "", doc_type: str | None = None, limit: int = 20
    ) -> list[DocumentVersion]:
        """Search documents by number, name, or type."""
        pass

    @abstractmethod
    def create_document(
        self,
        doc_number: str,
        name: str,
        doc_type: DocType,
        file_name: str | None = None,
        file_size_bytes: int | None = None,
        mime_type: str | None = None,
    ) -> DocumentVersion:
        """Create a new document master and initial version A.1 in IN_WORK state."""
        pass

    @abstractmethod
    def link_document_to_part(
        self,
        part_number: str,
        doc_number: str,
        link_type: PartDocLinkType = PartDocLinkType.DESCRIBES,
    ) -> PartDocLink:
        """Associate a document to a part version."""
        pass

    # -------------------------------------------------------------------------
    # Change Management (ECR & ECN)
    # -------------------------------------------------------------------------

    @abstractmethod
    def create_change_request(
        self,
        title: str,
        description: str,
        category: ChangeCategory,
        priority: ChangePriority,
        affected_parts: list[str],
    ) -> ChangeRequest:
        """Create an Engineering Change Request (ECR)."""
        pass

    @abstractmethod
    def get_change_request(self, cr_number: str) -> ChangeRequest | None:
        """Retrieve Change Request by CR number."""
        pass

    @abstractmethod
    def create_change_notice(
        self,
        title: str,
        description: str,
        cr_number: str | None = None,
    ) -> ChangeNotice:
        """Create an Engineering Change Notice (ECN)."""
        pass

    @abstractmethod
    def get_change_notice(self, cn_number: str) -> ChangeNotice | None:
        """Retrieve Change Notice by CN number."""
        pass

    @abstractmethod
    def add_change_affected_item(
        self,
        cn_number: str,
        item_type: str,
        item_number: str,
        disposition: ItemDisposition,
    ) -> ChangeAffectedItem:
        """Add an affected item to a Change Notice with disposition."""
        pass

    @abstractmethod
    def execute_change_notice(self, cn_number: str) -> ChangeNotice:
        """Execute and complete an approved Change Notice."""
        pass

    # -------------------------------------------------------------------------
    # Supplier & Sourcing Management (AML/AVL)
    # -------------------------------------------------------------------------

    @abstractmethod
    def search_manufacturers(
        self, query: str = "", status: str | None = None
    ) -> list[Manufacturer]:
        """Search registered manufacturers."""
        pass

    @abstractmethod
    def get_part_aml(self, part_number: str) -> list[AMLLink]:
        """Retrieve the Approved Manufacturer List (AML) for a part."""
        pass

    @abstractmethod
    def add_manufacturer(
        self, name: str, cage_code: str | None = None, country: str = "USA"
    ) -> Manufacturer:
        """Register a new external manufacturer."""
        pass

    @abstractmethod
    def add_manufacturer_part(
        self, mfr_name: str, mfr_part_number: str, description: str = ""
    ) -> ManufacturerPart:
        """Register a manufacturer part under a specific manufacturer."""
        pass

    @abstractmethod
    def set_sourcing_link(
        self,
        part_number: str,
        mfr_name: str,
        mfr_part_number: str,
        status: SourcingStatus,
        preference_rank: int = 1,
    ) -> AMLLink:
        """Associate an internal part to a manufacturer part with sourcing status."""
        pass

