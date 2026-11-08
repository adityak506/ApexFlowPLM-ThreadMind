"""Tool registration and export module."""

from plm_mcp.tools.bom import (
    add_bom_component,
    get_part_bom,
    get_where_used,
    remove_bom_component,
)
from plm_mcp.tools.changes import (
    add_change_affected_item,
    create_change_notice,
    create_change_request,
    execute_change_notice,
    get_change_notice,
    get_change_request,
)
from plm_mcp.tools.common import MutationResult
from plm_mcp.tools.documents import (
    create_document,
    get_document,
    link_document_to_part,
    search_documents,
)
from plm_mcp.tools.parts import (
    create_part,
    get_part,
    iterate_part,
    revise_part,
    search_parts,
    set_part_lifecycle_state,
)
from plm_mcp.tools.suppliers import (
    add_manufacturer,
    add_manufacturer_part,
    get_part_aml,
    search_manufacturers,
    set_sourcing_link,
)

__all__ = [
    "MutationResult",
    "get_part",
    "search_parts",
    "create_part",
    "revise_part",
    "iterate_part",
    "set_part_lifecycle_state",
    "get_part_bom",
    "get_where_used",
    "add_bom_component",
    "remove_bom_component",
    "get_document",
    "search_documents",
    "create_document",
    "link_document_to_part",
    "create_change_request",
    "get_change_request",
    "create_change_notice",
    "get_change_notice",
    "add_change_affected_item",
    "execute_change_notice",
    "search_manufacturers",
    "get_part_aml",
    "add_manufacturer",
    "add_manufacturer_part",
    "set_sourcing_link",
]

