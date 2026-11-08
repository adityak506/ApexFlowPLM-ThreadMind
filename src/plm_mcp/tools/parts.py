"""Part lifecycle, search, and revision MCP tools."""

from plm_mcp.backend import get_backend
from plm_mcp.models import LifecycleState, PartDetail, PartSummary
from plm_mcp.tools.common import MutationResult


def get_part(part_number: str, version: str | None = None) -> PartDetail | dict[str, str]:
    """Retrieve full details of a part version including BOM, document, and AML link counts.

    Args:
        part_number: The unique part identification number (e.g. 'DRN-1000').
        version: Optional version label (e.g. 'A.1' or 'B.1'). If omitted, retrieves the latest iteration.

    Returns:
        PartDetail object containing Master identity, Version metadata, and association counts,
        or error dictionary if not found.
    """
    backend = get_backend()
    part = backend.get_part(part_number, version)
    if not part:
        return {"error": f"Part '{part_number}' (version: {version or 'latest'}) not found."}
    return part


def search_parts(
    query: str = "", lifecycle_state: str | None = None, limit: int = 20
) -> list[PartSummary]:
    """Search parts by part number, name, or description with optional state filter.

    Args:
        query: Substring to match against part number, name, or description.
        lifecycle_state: Optional lifecycle state filter ('IN_WORK', 'UNDER_REVIEW', 'RELEASED', 'OBSOLETE').
        limit: Maximum number of search results to return (default 20).

    Returns:
        List of PartSummary records matching the criteria.
    """
    backend = get_backend()
    return backend.search_parts(query=query, lifecycle_state=lifecycle_state, limit=limit)


def create_part(
    part_number: str, name: str, description: str = "", confirm: bool = False
) -> MutationResult:
    """Create a new part master and initial version A.1 in IN_WORK state.

    Args:
        part_number: Unique part number (e.g. 'PRT-9001').
        name: Human-readable part name.
        description: Functional description or engineering specifications.
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or created PartVersion record.
    """
    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="create_part",
            message=f"DRY RUN: Part '{part_number}' ({name}) will be created at revision A.1 in state IN_WORK.",
            preview_data={
                "part_number": part_number,
                "name": name,
                "version_label": "A.1",
                "lifecycle_state": "IN_WORK",
                "description": description,
            },
        )

    backend = get_backend()
    part_version = backend.create_part(part_number=part_number, name=name, description=description)
    return MutationResult(
        success=True,
        is_dry_run=False,
        action="create_part",
        message=f"Part '{part_number}' successfully created at revision {part_version.version_label}.",
        applied_data=part_version.model_dump(),
    )


def iterate_part(
    part_number: str, description: str = "", confirm: bool = False
) -> MutationResult:
    """Increment the iteration number of an IN_WORK part (e.g. A.1 -> A.2), preserving BOM and associations.

    Args:
        part_number: The part number to iterate.
        description: Description of iteration changes.
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or iterated PartVersion record.
    """
    backend = get_backend()
    part = backend.get_part(part_number)
    if not part:
        return MutationResult(
            success=False,
            is_dry_run=not confirm,
            action="iterate_part",
            message=f"Part '{part_number}' does not exist.",
        )

    next_it = part.version.iteration + 1
    next_label = f"{part.version.revision}.{next_it}"

    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="iterate_part",
            message=f"DRY RUN: Part '{part_number}' will be iterated from {part.version.version_label} to {next_label}.",
            preview_data={
                "part_number": part_number,
                "current_version": part.version.version_label,
                "next_version": next_label,
                "lifecycle_state": part.version.lifecycle_state.value,
                "description": description or part.version.description,
            },
        )

    try:
        new_v = backend.iterate_part(part_number=part_number, description=description)
        return MutationResult(
            success=True,
            is_dry_run=False,
            action="iterate_part",
            message=f"Part '{part_number}' successfully iterated to {new_v.version_label}.",
            applied_data=new_v.model_dump(),
        )
    except Exception as e:
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="iterate_part",
            message=f"Failed to iterate part '{part_number}': {str(e)}",
        )


def revise_part(
    part_number: str, description: str = "", confirm: bool = False
) -> MutationResult:
    """Create a new major revision (e.g. A.2 -> B.1) in IN_WORK state for a RELEASED part.

    Args:
        part_number: The part number to revise.
        description: Description or reason for revision.
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or revised PartVersion record.
    """
    backend = get_backend()
    part = backend.get_part(part_number)
    if not part:
        return MutationResult(
            success=False,
            is_dry_run=not confirm,
            action="revise_part",
            message=f"Part '{part_number}' does not exist.",
        )

    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="revise_part",
            message=f"DRY RUN: Part '{part_number}' ({part.version.version_label}) will be revised to the next revision letter iteration 1 in IN_WORK state.",
            preview_data={
                "part_number": part_number,
                "current_version": part.version.version_label,
                "current_state": part.version.lifecycle_state.value,
                "new_iteration": 1,
                "target_state": "IN_WORK",
            },
        )

    try:
        new_v = backend.revise_part(part_number=part_number, description=description)
        return MutationResult(
            success=True,
            is_dry_run=False,
            action="revise_part",
            message=f"Part '{part_number}' successfully revised to {new_v.version_label}.",
            applied_data=new_v.model_dump(),
        )
    except Exception as e:
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="revise_part",
            message=f"Failed to revise part '{part_number}': {str(e)}",
        )


def set_part_lifecycle_state(
    part_number: str, target_state: str, confirm: bool = False
) -> MutationResult:
    """Transition a part's lifecycle state (IN_WORK -> UNDER_REVIEW -> RELEASED -> OBSOLETE).

    Args:
        part_number: The part number to transition.
        target_state: Target state name ('IN_WORK', 'UNDER_REVIEW', 'RELEASED', 'OBSOLETE').
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or updated PartVersion record.
    """
    try:
        state_enum = LifecycleState(target_state.upper())
    except ValueError:
        return MutationResult(
            success=False,
            is_dry_run=not confirm,
            action="set_part_lifecycle_state",
            message=f"Invalid target state '{target_state}'. Valid states: {[s.value for s in LifecycleState]}",
        )

    backend = get_backend()
    part = backend.get_part(part_number)
    if not part:
        return MutationResult(
            success=False,
            is_dry_run=not confirm,
            action="set_part_lifecycle_state",
            message=f"Part '{part_number}' does not exist.",
        )

    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="set_part_lifecycle_state",
            message=f"DRY RUN: Part '{part_number}' ({part.version.version_label}) will transition from {part.version.lifecycle_state.value} to {state_enum.value}.",
            preview_data={
                "part_number": part_number,
                "version_label": part.version.version_label,
                "from_state": part.version.lifecycle_state.value,
                "to_state": state_enum.value,
            },
        )

    try:
        updated_v = backend.set_part_lifecycle_state(part_number=part_number, target_state=state_enum)
        return MutationResult(
            success=True,
            is_dry_run=False,
            action="set_part_lifecycle_state",
            message=f"Part '{part_number}' successfully transitioned to {updated_v.lifecycle_state.value}.",
            applied_data=updated_v.model_dump(),
        )
    except Exception as e:
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="set_part_lifecycle_state",
            message=f"Lifecycle transition failed: {str(e)}",
        )

