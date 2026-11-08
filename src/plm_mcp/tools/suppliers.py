"""Supplier, Manufacturer, and Approved Manufacturer List (AML) MCP tools."""

from plm_mcp.backend import get_backend
from plm_mcp.models import AMLLink, Manufacturer, SourcingStatus
from plm_mcp.tools.common import MutationResult


def search_manufacturers(
    query: str = "", status: str | None = None
) -> list[Manufacturer]:
    """Search registered manufacturers by name or CAGE code with optional status filtering.

    Args:
        query: Substring to match against manufacturer name or CAGE code.
        status: Optional status filter ('ACTIVE', 'INACTIVE', 'RESTRICTED').

    Returns:
        List of matching Manufacturer records.
    """
    backend = get_backend()
    return backend.search_manufacturers(query=query, status=status)


def get_part_aml(part_number: str) -> list[AMLLink]:
    """Retrieve the Approved Manufacturer List (AML/AVL) for an internal part.

    Args:
        part_number: Internal part number to query (e.g. 'DRN-3010').

    Returns:
        List of AMLLink records with sourcing status ('PREFERRED', 'APPROVED', 'DO_NOT_USE') and rank.
    """
    backend = get_backend()
    return backend.get_part_aml(part_number=part_number)


def add_manufacturer(
    name: str, cage_code: str | None = None, country: str = "USA", confirm: bool = False
) -> MutationResult:
    """Register a new external manufacturer or vendor organization.

    Args:
        name: Official company name.
        cage_code: Commercial and Government Entity code (e.g. '7TM01').
        country: Country of incorporation/headquarters (default 'USA').
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or registered Manufacturer record.
    """
    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="add_manufacturer",
            message=f"DRY RUN: Manufacturer '{name}' (CAGE: {cage_code or 'N/A'}, Country: {country}) will be registered.",
            preview_data={
                "name": name,
                "cage_code": cage_code,
                "country": country,
                "status": "ACTIVE",
            },
        )

    backend = get_backend()
    try:
        mfr = backend.add_manufacturer(name=name, cage_code=cage_code, country=country)
        return MutationResult(
            success=True,
            is_dry_run=False,
            action="add_manufacturer",
            message=f"Manufacturer '{name}' successfully registered.",
            applied_data=mfr.model_dump(),
        )
    except Exception as e:
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="add_manufacturer",
            message=f"Failed to add manufacturer: {str(e)}",
        )


def add_manufacturer_part(
    mfr_name: str, mfr_part_number: str, description: str = "", confirm: bool = False
) -> MutationResult:
    """Register a manufacturer's commercial part number in the vendor catalog.

    Args:
        mfr_name: Registered manufacturer name.
        mfr_part_number: External catalog part number (e.g. 'F60-PRO-IV-1750KV').
        description: Component description or specs.
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or created ManufacturerPart record.
    """
    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="add_manufacturer_part",
            message=f"DRY RUN: Catalog part '{mfr_part_number}' under '{mfr_name}' will be added.",
            preview_data={
                "manufacturer_name": mfr_name,
                "mfr_part_number": mfr_part_number,
                "description": description,
            },
        )

    backend = get_backend()
    try:
        mp = backend.add_manufacturer_part(
            mfr_name=mfr_name,
            mfr_part_number=mfr_part_number,
            description=description,
        )
        return MutationResult(
            success=True,
            is_dry_run=False,
            action="add_manufacturer_part",
            message=f"Manufacturer part '{mfr_part_number}' successfully registered under '{mfr_name}'.",
            applied_data=mp.model_dump(),
        )
    except Exception as e:
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="add_manufacturer_part",
            message=f"Failed to add manufacturer part: {str(e)}",
        )


def set_sourcing_link(
    part_number: str,
    mfr_name: str,
    mfr_part_number: str,
    status: str = "APPROVED",
    preference_rank: int = 1,
    confirm: bool = False,
) -> MutationResult:
    """Link an external manufacturer part to an internal part with an AML approval status.

    Args:
        part_number: Internal part number (e.g. 'DRN-3010').
        mfr_name: Manufacturer name.
        mfr_part_number: Manufacturer's catalog part number.
        status: Approval status ('PREFERRED', 'APPROVED', 'DO_NOT_USE', 'UNDER_REVIEW').
        preference_rank: Sourcing priority rank (1 = primary choice).
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or created AMLLink record.
    """
    try:
        status_enum = SourcingStatus(status.upper())
    except ValueError:
        return MutationResult(
            success=False,
            is_dry_run=not confirm,
            action="set_sourcing_link",
            message=f"Invalid sourcing status '{status}'. Valid: {[s.value for s in SourcingStatus]}",
        )

    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="set_sourcing_link",
            message=f"DRY RUN: Link '{mfr_name}' ({mfr_part_number}) -> '{part_number}' with status '{status_enum.value}' and rank {preference_rank}.",
            preview_data={
                "internal_part_number": part_number,
                "manufacturer_name": mfr_name,
                "mfr_part_number": mfr_part_number,
                "sourcing_status": status_enum.value,
                "preference_rank": preference_rank,
            },
        )

    backend = get_backend()
    try:
        link = backend.set_sourcing_link(
            part_number=part_number,
            mfr_name=mfr_name,
            mfr_part_number=mfr_part_number,
            status=status_enum,
            preference_rank=preference_rank,
        )
        return MutationResult(
            success=True,
            is_dry_run=False,
            action="set_sourcing_link",
            message=f"Successfully linked '{mfr_part_number}' to '{part_number}' as {status_enum.value}.",
            applied_data=link.model_dump(),
        )
    except Exception as e:
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="set_sourcing_link",
            message=f"Failed to set sourcing link: {str(e)}",
        )

