"""PTC Windchill REST / OData backend implementation stub.

All endpoints are marked with 'TODO: verify against Windchill docs' in accordance
with project rules. No endpoints are invented.
"""

from plm_mcp.backend.base import PLMBackend
from plm_mcp.config import settings
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


class WindchillBackend(PLMBackend):
    """PTC Windchill enterprise backend interacting via Windchill REST Services (WRS)."""

    def __init__(self) -> None:
        self.base_url = settings.windchill_base_url
        self.username = settings.windchill_username
        self.password = settings.windchill_password
        self.container = settings.windchill_container
        # TODO: verify against Windchill docs (Windchill REST Services / PTC OData auth headers)
        self._validate_credentials()

    def _validate_credentials(self) -> None:
        if not self.base_url:
            # Informational check; allows instantiated stub in test environments
            pass

    # -------------------------------------------------------------------------
    # Part Management
    # -------------------------------------------------------------------------

    def get_part(
        self, part_number: str, version: str | None = None
    ) -> PartDetail | None:
        # TODO: verify against Windchill docs (Endpoint: /Windchill/servlet/odata/ProdMgmt/Parts?$filter=Number eq '{part_number}')
        raise NotImplementedError(
            "Windchill REST integration is pending live server endpoint verification. "
            "TODO: verify against Windchill docs"
        )

    def search_parts(
        self,
        query: str = "",
        lifecycle_state: str | None = None,
        limit: int = 20,
    ) -> list[PartSummary]:
        # TODO: verify against Windchill docs (Endpoint: /Windchill/servlet/odata/ProdMgmt/Parts)
        raise NotImplementedError(
            "Windchill search query requires PTC WRS catalog verification. "
            "TODO: verify against Windchill docs"
        )

    def create_part(
        self, part_number: str, name: str, description: str = ""
    ) -> PartVersion:
        # TODO: verify against Windchill docs (POST /Windchill/servlet/odata/ProdMgmt/Parts)
        raise NotImplementedError(
            "Windchill part creation payload schema requires WRS verification. "
            "TODO: verify against Windchill docs"
        )

    def revise_part(
        self, part_number: str, description: str = ""
    ) -> PartVersion:
        # TODO: verify against Windchill docs (Action: /Windchill/servlet/odata/ProdMgmt/Parts('{id}')/PTC.ProdMgmt.Revise)
        raise NotImplementedError(
            "Windchill revise action requires PTC OData action verification. "
            "TODO: verify against Windchill docs"
        )

    def iterate_part(
        self, part_number: str, description: str = ""
    ) -> PartVersion:
        # TODO: verify against Windchill docs (Action: /Windchill/servlet/odata/ProdMgmt/Parts('{id}')/PTC.ProdMgmt.CheckOut and CheckIn)
        raise NotImplementedError(
            "Windchill iteration uses CheckOut/CheckIn semantics. "
            "TODO: verify against Windchill docs"
        )

    def set_part_lifecycle_state(
        self, part_number: str, target_state: LifecycleState
    ) -> PartVersion:
        # TODO: verify against Windchill docs (Action: /Windchill/servlet/odata/ProdMgmt/Parts('{id}')/PTC.ProdMgmt.SetLifeCycleState)
        raise NotImplementedError(
            "Windchill lifecycle promotion requires SetLifeCycleState action verification. "
            "TODO: verify against Windchill docs"
        )

    # -------------------------------------------------------------------------
    # Bill of Materials (BOM)
    # -------------------------------------------------------------------------

    def get_part_bom(
        self, part_number: str, levels: int = 1, version: str | None = None
    ) -> BOMNode | None:
        # TODO: verify against Windchill docs (Navigation: /Windchill/servlet/odata/ProdMgmt/Parts('{id}')/PartStructure)
        raise NotImplementedError(
            "Windchill PartStructure navigation requires OData schema verification. "
            "TODO: verify against Windchill docs"
        )

    def get_where_used(
        self, part_number: str, top_level_only: bool = False
    ) -> list[WhereUsedItem]:
        # TODO: verify against Windchill docs (Navigation: /Windchill/servlet/odata/ProdMgmt/Parts('{id}')/UsedIn)
        raise NotImplementedError(
            "Windchill WhereUsed query requires WRS endpoint verification. "
            "TODO: verify against Windchill docs"
        )

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
        # TODO: verify against Windchill docs (Endpoint: /Windchill/servlet/odata/ProdMgmt/Parts('{id}')/PartUses)
        raise NotImplementedError(
            "Windchill PartUses link creation requires WRS payload verification. "
            "TODO: verify against Windchill docs"
        )

    def remove_bom_component(
        self, parent_part_number: str, child_part_number: str
    ) -> bool:
        # TODO: verify against Windchill docs (DELETE /Windchill/servlet/odata/ProdMgmt/PartUses('{id}'))
        raise NotImplementedError(
            "Windchill PartUses deletion requires WRS payload verification. "
            "TODO: verify against Windchill docs"
        )

    # -------------------------------------------------------------------------
    # Document Management
    # -------------------------------------------------------------------------

    def get_document(
        self, doc_number: str, version: str | None = None
    ) -> DocumentVersion | None:
        # TODO: verify against Windchill docs (Endpoint: /Windchill/servlet/odata/DocMgmt/Documents?$filter=Number eq '{doc_number}')
        raise NotImplementedError(
            "Windchill DocMgmt endpoint requires WRS verification. "
            "TODO: verify against Windchill docs"
        )

    def search_documents(
        self, query: str = "", doc_type: str | None = None, limit: int = 20
    ) -> list[DocumentVersion]:
        # TODO: verify against Windchill docs (Endpoint: /Windchill/servlet/odata/DocMgmt/Documents)
        raise NotImplementedError(
            "Windchill DocMgmt search requires WRS query parameter verification. "
            "TODO: verify against Windchill docs"
        )

    def create_document(
        self,
        doc_number: str,
        name: str,
        doc_type: DocType,
        file_name: str | None = None,
        file_size_bytes: int | None = None,
        mime_type: str | None = None,
    ) -> DocumentVersion:
        # TODO: verify against Windchill docs (POST /Windchill/servlet/odata/DocMgmt/Documents)
        raise NotImplementedError(
            "Windchill Document creation and attachment upload requires WRS attachment verification. "
            "TODO: verify against Windchill docs"
        )

    def link_document_to_part(
        self,
        part_number: str,
        doc_number: str,
        link_type: PartDocLinkType = PartDocLinkType.DESCRIBES,
    ) -> PartDocLink:
        # TODO: verify against Windchill docs (POST /Windchill/servlet/odata/ProdMgmt/Parts('{id}')/DescribedByDocuments)
        raise NotImplementedError(
            "Windchill Part-Document association requires DescribedBy/ReferencedBy verification. "
            "TODO: verify against Windchill docs"
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
        # TODO: verify against Windchill docs (Endpoint: /Windchill/servlet/odata/ChangeMgmt/ChangeRequests)
        raise NotImplementedError(
            "Windchill ChangeRequests OData entity requires verification. "
            "TODO: verify against Windchill docs"
        )

    def get_change_request(self, cr_number: str) -> ChangeRequest | None:
        # TODO: verify against Windchill docs (Endpoint: /Windchill/servlet/odata/ChangeMgmt/ChangeRequests?$filter=Number eq '{cr_number}')
        raise NotImplementedError(
            "Windchill ChangeRequests retrieval requires WRS verification. "
            "TODO: verify against Windchill docs"
        )

    def create_change_notice(
        self,
        title: str,
        description: str,
        cr_number: str | None = None,
    ) -> ChangeNotice:
        # TODO: verify against Windchill docs (Endpoint: /Windchill/servlet/odata/ChangeMgmt/ChangeOrders)
        raise NotImplementedError(
            "Windchill ChangeOrders entity schema requires verification. "
            "TODO: verify against Windchill docs"
        )

    def get_change_notice(self, cn_number: str) -> ChangeNotice | None:
        # TODO: verify against Windchill docs (Endpoint: /Windchill/servlet/odata/ChangeMgmt/ChangeOrders?$filter=Number eq '{cn_number}')
        raise NotImplementedError(
            "Windchill ChangeOrders retrieval requires WRS verification. "
            "TODO: verify against Windchill docs"
        )

    def add_change_affected_item(
        self,
        cn_number: str,
        item_type: str,
        item_number: str,
        disposition: ItemDisposition,
    ) -> ChangeAffectedItem:
        # TODO: verify against Windchill docs (Endpoint: /Windchill/servlet/odata/ChangeMgmt/ChangeOrders('{id}')/AffectedItems)
        raise NotImplementedError(
            "Windchill AffectedItems association requires schema verification. "
            "TODO: verify against Windchill docs"
        )

    def execute_change_notice(self, cn_number: str) -> ChangeNotice:
        # TODO: verify against Windchill docs (Action: /Windchill/servlet/odata/ChangeMgmt/ChangeOrders('{id}')/PTC.ChangeMgmt.Complete)
        raise NotImplementedError(
            "Windchill change order workflow resolution requires state machine verification. "
            "TODO: verify against Windchill docs"
        )

    # -------------------------------------------------------------------------
    # Supplier & Sourcing Management (AML/AVL)
    # -------------------------------------------------------------------------

    def search_manufacturers(
        self, query: str = "", status: str | None = None
    ) -> list[Manufacturer]:
        # TODO: verify against Windchill docs (Endpoint: /Windchill/servlet/odata/SourcingMgmt/Manufacturers)
        raise NotImplementedError(
            "Windchill SourcingMgmt Manufacturers entity requires verification. "
            "TODO: verify against Windchill docs"
        )

    def get_part_aml(self, part_number: str) -> list[AMLLink]:
        # TODO: verify against Windchill docs (Navigation: /Windchill/servlet/odata/ProdMgmt/Parts('{id}')/ApprovedManufacturers)
        raise NotImplementedError(
            "Windchill AXLLink / ApprovedManufacturers query requires verification. "
            "TODO: verify against Windchill docs"
        )

    def add_manufacturer(
        self, name: str, cage_code: str | None = None, country: str = "USA"
    ) -> Manufacturer:
        # TODO: verify against Windchill docs (POST /Windchill/servlet/odata/SourcingMgmt/Manufacturers)
        raise NotImplementedError(
            "Windchill Manufacturer creation requires schema verification. "
            "TODO: verify against Windchill docs"
        )

    def add_manufacturer_part(
        self, mfr_name: str, mfr_part_number: str, description: str = ""
    ) -> ManufacturerPart:
        # TODO: verify against Windchill docs (POST /Windchill/servlet/odata/SourcingMgmt/ManufacturerParts)
        raise NotImplementedError(
            "Windchill ManufacturerParts entity requires verification. "
            "TODO: verify against Windchill docs"
        )

    def set_sourcing_link(
        self,
        part_number: str,
        mfr_name: str,
        mfr_part_number: str,
        status: SourcingStatus,
        preference_rank: int = 1,
    ) -> AMLLink:
        # TODO: verify against Windchill docs (POST /Windchill/servlet/odata/SourcingMgmt/AXLLinks)
        raise NotImplementedError(
            "Windchill AXLLink creation requires verification. "
            "TODO: verify against Windchill docs"
        )

