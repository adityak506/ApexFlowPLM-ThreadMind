"""Change management MCP tools for Engineering Change Requests (ECR) and Notices (ECN)."""

from plm_mcp.backend import get_backend
from plm_mcp.models import (
    ChangeCategory,
    ChangeNotice,
    ChangePriority,
    ChangeRequest,
    ItemDisposition,
)
from plm_mcp.tools.common import MutationResult


def get_change_request(cr_number: str) -> ChangeRequest | dict[str, str]:
    """Retrieve details of an Engineering Change Request (ECR) including impacted items.

    Args:
        cr_number: Unique change request identifier (e.g. 'CR-0001').

    Returns:
        ChangeRequest object or error dictionary if not found.
    """
    backend = get_backend()
    cr = backend.get_change_request(cr_number=cr_number)
    if not cr:
        return {"error": f"Change Request '{cr_number}' not found."}
    return cr


def create_change_request(
    title: str,
    description: str,
    category: str = "DESIGN_IMPROVEMENT",
    priority: str = "MEDIUM",
    affected_parts: list[str] = [],
    confirm: bool = False,
) -> MutationResult:
    """Submit a new Engineering Change Request (ECR) documenting a product issue or improvement.

    Args:
        title: Summary title of the requested change.
        description: Detailed rationale, problem description, or proposed solution.
        category: Change classification ('DESIGN_IMPROVEMENT', 'DEFECT', 'COST_REDUCTION', 'COMPLIANCE').
        priority: Urgency level ('LOW', 'MEDIUM', 'HIGH', 'EMERGENCY').
        affected_parts: List of part numbers potentially impacted by this request.
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or created ChangeRequest record.
    """
    try:
        cat_enum = ChangeCategory(category.upper())
    except ValueError:
        return MutationResult(
            success=False,
            is_dry_run=not confirm,
            action="create_change_request",
            message=f"Invalid category '{category}'. Valid: {[c.value for c in ChangeCategory]}",
        )

    try:
        pri_enum = ChangePriority(priority.upper())
    except ValueError:
        return MutationResult(
            success=False,
            is_dry_run=not confirm,
            action="create_change_request",
            message=f"Invalid priority '{priority}'. Valid: {[p.value for p in ChangePriority]}",
        )

    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="create_change_request",
            message=f"DRY RUN: Change Request '{title}' (Category: {cat_enum.value}, Priority: {pri_enum.value}) will be created.",
            preview_data={
                "title": title,
                "description": description,
                "category": cat_enum.value,
                "priority": pri_enum.value,
                "affected_parts": affected_parts,
            },
        )

    backend = get_backend()
    try:
        cr = backend.create_change_request(
            title=title,
            description=description,
            category=cat_enum,
            priority=pri_enum,
            affected_parts=affected_parts,
        )
        return MutationResult(
            success=True,
            is_dry_run=False,
            action="create_change_request",
            message=f"Change Request '{cr.cr_number}' successfully created.",
            applied_data=cr.model_dump(),
        )
    except Exception as e:
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="create_change_request",
            message=f"Failed to create change request: {str(e)}",
        )


def get_change_notice(cn_number: str) -> ChangeNotice | dict[str, str]:
    """Retrieve details of an Engineering Change Notice (ECN) including dispositions and resulting items.

    Args:
        cn_number: Unique change notice identifier (e.g. 'CN-0001').

    Returns:
        ChangeNotice object or error dictionary if not found.
    """
    backend = get_backend()
    cn = backend.get_change_notice(cn_number=cn_number)
    if not cn:
        return {"error": f"Change Notice '{cn_number}' not found."}
    return cn


def create_change_notice(
    title: str,
    description: str,
    cr_number: str | None = None,
    confirm: bool = False,
) -> MutationResult:
    """Create an Engineering Change Notice (ECN) to authorize and execute design changes.

    Args:
        title: Title of the change notice.
        description: Implementation plan and execution details.
        cr_number: Optional parent Change Request (ECR) number being resolved.
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or created ChangeNotice record.
    """
    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="create_change_notice",
            message=f"DRY RUN: Change Notice '{title}' (Parent CR: {cr_number or 'None'}) will be created.",
            preview_data={
                "title": title,
                "description": description,
                "cr_number": cr_number,
                "initial_state": "OPEN",
            },
        )

    backend = get_backend()
    try:
        cn = backend.create_change_notice(
            title=title,
            description=description,
            cr_number=cr_number,
        )
        return MutationResult(
            success=True,
            is_dry_run=False,
            action="create_change_notice",
            message=f"Change Notice '{cn.cn_number}' successfully created.",
            applied_data=cn.model_dump(),
        )
    except Exception as e:
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="create_change_notice",
            message=f"Failed to create change notice: {str(e)}",
        )


def add_change_affected_item(
    cn_number: str,
    item_type: str,
    item_number: str,
    disposition: str = "USE_AS_IS",
    confirm: bool = False,
) -> MutationResult:
    """Add an affected item (part or document) to a Change Notice with a disposition directive.

    Args:
        cn_number: Change notice number to update.
        item_type: Type of item ('PART' or 'DOCUMENT').
        item_number: Number of the affected item (e.g. 'DRN-4010').
        disposition: Material disposition ('SCRAP', 'REWORK', 'USE_AS_IS').
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or created ChangeAffectedItem record.
    """
    try:
        disp_enum = ItemDisposition(disposition.upper())
    except ValueError:
        return MutationResult(
            success=False,
            is_dry_run=not confirm,
            action="add_change_affected_item",
            message=f"Invalid disposition '{disposition}'. Valid: {[d.value for d in ItemDisposition]}",
        )

    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="add_change_affected_item",
            message=f"DRY RUN: {item_type.upper()} '{item_number}' will be attached to '{cn_number}' with disposition '{disp_enum.value}'.",
            preview_data={
                "cn_number": cn_number,
                "item_type": item_type.upper(),
                "item_number": item_number,
                "disposition": disp_enum.value,
            },
        )

    backend = get_backend()
    try:
        aff = backend.add_change_affected_item(
            cn_number=cn_number,
            item_type=item_type,
            item_number=item_number,
            disposition=disp_enum,
        )
        return MutationResult(
            success=True,
            is_dry_run=False,
            action="add_change_affected_item",
            message=f"Successfully attached {item_type.upper()} '{item_number}' to '{cn_number}'.",
            applied_data=aff.model_dump(),
        )
    except Exception as e:
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="add_change_affected_item",
            message=f"Failed to attach affected item: {str(e)}",
        )


def execute_change_notice(
    cn_number: str, confirm: bool = False
) -> MutationResult:
    """Execute and finalize an approved Change Notice, updating affected item lifecycles and resolving parent CR.

    Args:
        cn_number: Change notice number to execute.
        confirm: Safety gate. Must be True to persist changes. Defaults to False (dry-run).

    Returns:
        MutationResult containing dry-run preview or updated completed ChangeNotice record.
    """
    backend = get_backend()
    cn = backend.get_change_notice(cn_number)
    if not cn:
        return MutationResult(
            success=False,
            is_dry_run=not confirm,
            action="execute_change_notice",
            message=f"Change notice '{cn_number}' does not exist.",
        )

    if not confirm:
        return MutationResult(
            success=True,
            is_dry_run=True,
            action="execute_change_notice",
            message=f"DRY RUN: Change notice '{cn_number}' will be finalized. Affected items will be dispositioned and state set to COMPLETED.",
            preview_data={
                "cn_number": cn_number,
                "current_state": cn.state.value,
                "target_state": "COMPLETED",
                "affected_items_count": len(cn.affected_items),
            },
        )

    try:
        completed_cn = backend.execute_change_notice(cn_number=cn_number)
        return MutationResult(
            success=True,
            is_dry_run=False,
            action="execute_change_notice",
            message=f"Change Notice '{cn_number}' successfully executed and closed.",
            applied_data=completed_cn.model_dump(),
        )
    except Exception as e:
        return MutationResult(
            success=False,
            is_dry_run=False,
            action="execute_change_notice",
            message=f"Execution failed: {str(e)}",
        )

