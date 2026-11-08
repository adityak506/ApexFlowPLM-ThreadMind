"""Tests for Document MCP tools covering creation, search, and part associations."""

from plm_mcp.tools.documents import (
    create_document,
    get_document,
    link_document_to_part,
    search_documents,
)


def test_get_document():
    doc = get_document("DOC-SPEC-1000")
    assert not isinstance(doc, dict) or "error" not in doc
    assert doc.doc_number == "DOC-SPEC-1000"


def test_search_documents():
    docs = search_documents("Specification")
    assert len(docs) > 0


def test_create_document_dry_run_and_confirm():
    # Dry run
    dry = create_document("DOC-TST-01", "Draft Document", doc_type="CAD_DRAWING", confirm=False)
    assert dry.success is True
    assert dry.is_dry_run is True

    # Confirmed
    live = create_document("DOC-TST-01", "Draft Document", doc_type="CAD_DRAWING", confirm=True)
    assert live.success is True
    assert live.is_dry_run is False
    assert live.applied_data["doc_number"] == "DOC-TST-01"


def test_link_document_to_part():
    create_document("DOC-TST-02", "Wiring Diagram", doc_type="SPECIFICATION", confirm=True)

    # Dry run
    dry_link = link_document_to_part("DRN-1000", "DOC-TST-02", link_type="DESCRIBES", confirm=False)
    assert dry_link.success is True
    assert dry_link.is_dry_run is True

    # Confirmed
    live_link = link_document_to_part("DRN-1000", "DOC-TST-02", link_type="DESCRIBES", confirm=True)
    assert live_link.success is True
    assert live_link.is_dry_run is False

