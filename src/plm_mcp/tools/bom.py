"""Bill of Materials (BOM) management and explosion MCP tools."""

from plm_mcp.backend import get_backend
from plm_mcp.models import BOMNode, WhereUsedItem
from plm_mcp.tools.common import MutationResult


def get_part_bom(
    part_number: str, levels: int = 1, version: str | None = None
) -> BOMNode | dict[str, str]:
    """Retrieve single-level or multi-level indented Bill of Materials (BOM) tree for an assembly.

    Args:
        part_number: The parent assembly part number (e.g. 'DRN-1000').
        levels: Depth of BOM hierarchy explosion (default 1 for single-level, higher for multi-level).
        version: Specific revision/iteration label (e.g. 'A.1'). Defaults to latest.

    Returns:
        Hierarchical BOMNode structure with nested children, or error dictionary if not found.
    """
    backend = get_backend()
    bom = backend.get_part_bom(part_number=part_number, levels=levels, version=version)
    if not bom:
        return {"error": f"Part '{part_number}' not found or has no BOM structure."}
    return bom


def get_where_used(
    part_number: str, top_level_only: bool = False
) -> list[WhereUsedItem]:
    """Find all parent assemblies that consume this component in their BOM usage links.

    Args:
        part_number: The component part number to analyze (e.g. 'DRN-3010').
        top_level_only: If True, filters only to root top-level assemblies.

    Returns:
        List of WhereUsedItem records showing consuming parents, quantities, and units.
    """
    backend = get_backend()
    return backend.get_where_used(part_number=part_number, top_level_only=top_level_only)


def add_bom_component(
    parent_part_number: str,
    child_part_number: str,
    quantity: float = 1.0,
    unit: str = "ea",
    find_number: int | None = None,
    ref_designators: str | None = None,
    notes: str = "",
    confirm: bool = False,
) -> MutationResult:
    """Add a child component usage link to an IN_WORK parent assembly.

    Args:
        parent_part_number: The assembly receiving the component (must be in state IN_WORK).
        child_part_number: The component part number to add as child.
        quantity: Usage quantity (default 1.0).
        unit: Unit of measure (e.g. 'ea', 'mm', 'g').
        find_number: Assembly line or balloon sequence number (e.g. 10, 20).
        ref_designators: Circuit or mechanical reference designators (e.g. 'R1, R2' or 'M1-M4').
        notes: Engineering usage link notes.
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or created BOMLink record.
    """
    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="add_bom_component",
            message=f"DRY RUN: Component '{child_part_number}' (Qty: {quantity} {unit}) will be linked under '{parent_part_number}'.",
            preview_data={
                "parent_part_number": parent_part_number,
                "child_part_number": child_part_number,
                "quantity": quantity,
                "unit": unit,
                "find_number": find_number,
                "ref_designators": ref_designators,
                "notes": notes,
            },
        )

    backend = get_backend()
    try:
        link = backend.add_bom_component(
            parent_part_number=parent_part_number,
            child_part_number=child_part_number,
            quantity=quantity,
            unit=unit,
            find_number=find_number,
            ref_designators=ref_designators,
            notes=notes,
        )
        return MutationResult(
            success=True,
            is_dry_run=False,
            action="add_bom_component",
            message=f"Successfully linked '{child_part_number}' into '{parent_part_number}'.",
            applied_data=link.model_dump(),
        )
    except Exception as e:
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="add_bom_component",
            message=f"Failed to add BOM component: {str(e)}",
        )


def remove_bom_component(
    parent_part_number: str, child_part_number: str, confirm: bool = False
) -> MutationResult:
    """Remove a child component usage link from an IN_WORK parent assembly.

    Args:
        parent_part_number: The assembly containing the component (must be in state IN_WORK).
        child_part_number: The component part number to remove.
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or removal confirmation.
    """
    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="remove_bom_component",
            message=f"DRY RUN: Component '{child_part_number}' will be removed from '{parent_part_number}'.",
            preview_data={
                "parent_part_number": parent_part_number,
                "child_part_number": child_part_number,
            },
        )

    backend = get_backend()
    try:
        removed = backend.remove_bom_component(
            parent_part_number=parent_part_number,
            child_part_number=child_part_number,
        )
        if removed:
            return MutationResult(
                success=True,
                is_dry_run=False,
                action="remove_bom_component",
                message=f"Successfully removed '{child_part_number}' from '{parent_part_number}'.",
                applied_data={"parent_part_number": parent_part_number, "child_part_number": child_part_number},
            )
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="remove_bom_component",
            message=f"Component '{child_part_number}' was not found in BOM of '{parent_part_number}'.",
        )
    except Exception as e:
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="remove_bom_component",
            message=f"Failed to remove BOM component: {str(e)}",
        )

