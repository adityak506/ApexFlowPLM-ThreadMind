"""Document management and part association MCP tools."""

from plm_mcp.backend import get_backend
from plm_mcp.models import DocType, DocumentVersion, PartDocLinkType
from plm_mcp.tools.common import MutationResult


def get_document(
    doc_number: str, version: str | None = None
) -> DocumentVersion | dict[str, str]:
    """Retrieve document metadata, lifecycle state, and vault file attachment info.

    Args:
        doc_number: The unique document identification number (e.g. 'DOC-SPEC-1000').
        version: Optional version label (e.g. 'A.1'). Defaults to latest iteration.

    Returns:
        DocumentVersion object or error dictionary if not found.
    """
    backend = get_backend()
    doc = backend.get_document(doc_number=doc_number, version=version)
    if not doc:
        return {"error": f"Document '{doc_number}' not found."}
    return doc


def search_documents(
    query: str = "", doc_type: str | None = None, limit: int = 20
) -> list[DocumentVersion]:
    """Search documents by number or name with optional document type filtering.

    Args:
        query: Substring to match against document number or name.
        doc_type: Optional classification filter ('SPECIFICATION', 'CAD_DRAWING', 'TEST_REPORT', 'USER_MANUAL').
        limit: Maximum number of search results to return (default 20).

    Returns:
        List of DocumentVersion objects matching criteria.
    """
    backend = get_backend()
    return backend.search_documents(query=query, doc_type=doc_type, limit=limit)


def create_document(
    doc_number: str,
    name: str,
    doc_type: str = "SPECIFICATION",
    file_name: str | None = None,
    file_size_bytes: int | None = None,
    mime_type: str | None = None,
    confirm: bool = False,
) -> MutationResult:
    """Create a new document master and initialize version A.1 in IN_WORK state.

    Args:
        doc_number: Unique document number (e.g. 'DOC-CAD-9999').
        name: Title of the document.
        doc_type: Document classification ('SPECIFICATION', 'CAD_DRAWING', 'TEST_REPORT', 'USER_MANUAL').
        file_name: Primary attachment file name.
        file_size_bytes: Size of primary attachment in bytes.
        mime_type: Media type of attachment (e.g. 'application/pdf').
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or created DocumentVersion record.
    """
    try:
        type_enum = DocType(doc_type.upper())
    except ValueError:
        return MutationResult(
            success=False,
            is_dry_run=not confirm,
            action="create_document",
            message=f"Invalid doc_type '{doc_type}'. Valid types: {[t.value for t in DocType]}",
        )

    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="create_document",
            message=f"DRY RUN: Document '{doc_number}' ({name}) of type {type_enum.value} will be created at revision A.1 in state IN_WORK.",
            preview_data={
                "doc_number": doc_number,
                "name": name,
                "doc_type": type_enum.value,
                "file_name": file_name,
                "version_label": "A.1",
                "lifecycle_state": "IN_WORK",
            },
        )

    backend = get_backend()
    try:
        doc = backend.create_document(
            doc_number=doc_number,
            name=name,
            doc_type=type_enum,
            file_name=file_name,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
        )
        return MutationResult(
            success=True,
            is_dry_run=False,
            action="create_document",
            message=f"Document '{doc_number}' successfully created at revision {doc.version_label}.",
            applied_data=doc.model_dump(),
        )
    except Exception as e:
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="create_document",
            message=f"Failed to create document: {str(e)}",
        )


def link_document_to_part(
    part_number: str,
    doc_number: str,
    link_type: str = "DESCRIBES",
    confirm: bool = False,
) -> MutationResult:
    """Create an association between a document and a part (e.g. CAD drawing or spec).

    Args:
        part_number: Part number receiving the association.
        doc_number: Document number to attach.
        link_type: Association semantics ('DESCRIBES' or 'REFERENCES').
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or created PartDocLink record.
    """
    try:
        link_enum = PartDocLinkType(link_type.upper())
    except ValueError:
        return MutationResult(
            success=False,
            is_dry_run=not confirm,
            action="link_document_to_part",
            message=f"Invalid link_type '{link_type}'. Valid types: {[t.value for t in PartDocLinkType]}",
        )

    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="link_document_to_part",
            message=f"DRY RUN: Document '{doc_number}' will be linked to part '{part_number}' with relationship '{link_enum.value}'.",
            preview_data={
                "part_number": part_number,
                "doc_number": doc_number,
                "link_type": link_enum.value,
            },
        )

    backend = get_backend()
    try:
        link = backend.link_document_to_part(
            part_number=part_number,
            doc_number=doc_number,
            link_type=link_enum,
        )
        return MutationResult(
            success=True,
            is_dry_run=False,
            action="link_document_to_part",
            message=f"Successfully linked document '{doc_number}' to part '{part_number}'.",
            applied_data=link.model_dump(),
        )
    except Exception as e:
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="link_document_to_part",
            message=f"Failed to link document: {str(e)}",
        )

