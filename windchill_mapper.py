"""PTC Windchill OData response mapper.

Maps raw PTC Windchill REST Services (WRS / OData v4) JSON payloads to normalized
PLM domain models (Part, BomLink, etc.) defined in plm_interface.py.

All unverified Windchill schema field names are marked with TODO comments
requiring verification against the target Windchill instance's $metadata.
"""

from datetime import datetime
from typing import Any

from plm_interface import BomLink, LifecycleState, Part


def map_windchill_state(raw_state: Any) -> LifecycleState:
    """Map Windchill lifecycle state string or complex object to normalized LifecycleState.

    # TODO: verify against Windchill docs / $metadata:
    # In WRS, State can be returned as an object {'Value': 'RELEASED', 'Display': 'Released'}
    # or as an enum string 'RELEASED' or 'LifeCycleState' property.
    """
    if not raw_state:
        return LifecycleState.IN_WORK

    if isinstance(raw_state, dict):
        state_str = str(raw_state.get("Value") or raw_state.get("Display") or "").strip().upper()
    else:
        state_str = str(raw_state).strip().upper()

    # Normalize state string variants
    if "RELEASE" in state_str:
        return LifecycleState.RELEASED
    elif "OBSOLETE" in state_str:
        return LifecycleState.OBSOLETE
    elif "REVIEW" in state_str or "UNDER_REVIEW" in state_str:
        return LifecycleState.UNDER_REVIEW
    elif "WORK" in state_str or "IN_WORK" in state_str or "INWORK" in state_str:
        return LifecycleState.IN_WORK
    return LifecycleState.IN_WORK


def map_windchill_version(raw: dict[str, Any]) -> tuple[str, int, str]:
    """Extract revision, iteration, and composite version_label from Windchill part payload.

    # TODO: verify against Windchill docs / $metadata:
    # WRS may expose 'VersionID' ('A.1'), or separate 'Version' ('A') and 'Iteration' (1).
    """
    version_id = raw.get("VersionID") or raw.get("version_label")
    if version_id and "." in str(version_id):
        parts = str(version_id).split(".", 1)
        revision = parts[0]
        try:
            iteration = int(parts[1])
        except ValueError:
            iteration = 1
        return revision, iteration, str(version_id)

    revision = str(raw.get("Version") or raw.get("revision") or "A").strip()
    try:
        iteration = int(raw.get("Iteration") or raw.get("iteration") or 1)
    except (ValueError, TypeError):
        iteration = 1

    version_label = f"{revision}.{iteration}"
    return revision, iteration, version_label


def map_windchill_make_buy(raw_source: Any) -> str:
    """Map Windchill Part Source to MAKE or BUY.

    # TODO: verify against Windchill docs / $metadata:
    # In WRS, Source may be {'Value': 'make', 'Display': 'Make'} or string 'make'/'buy'.
    """
    if isinstance(raw_source, dict):
        val = str(raw_source.get("Value") or raw_source.get("Display") or "").strip().upper()
    elif raw_source is not None:
        val = str(raw_source).strip().upper()
    else:
        val = "MAKE"

    return "BUY" if "BUY" in val else "MAKE"


def parse_windchill_timestamp(ts_raw: Any) -> datetime:
    """Parse Windchill ISO 8601 timestamp string into datetime."""
    if not ts_raw:
        return datetime.utcnow()
    if isinstance(ts_raw, datetime):
        return ts_raw
    try:
        # Strip trailing Z for fromisoformat if needed
        clean_ts = str(ts_raw).replace("Z", "+00:00")
        return datetime.fromisoformat(clean_ts)
    except Exception:
        return datetime.utcnow()


def map_windchill_part_to_normalized(raw: dict[str, Any]) -> Part:
    """Map a raw Windchill OData Part entity payload to normalized Part model.

    # TODO: verify against Windchill docs / $metadata:
    # Verify entity PTC.ProdMgmt.Part properties:
    # - 'Number' (unique part number)
    # - 'Name' (part title)
    # - 'Description' (specifications)
    # - 'State' or 'LifeCycleState' (lifecycle state machine)
    # - 'Source' (make/buy designation)
    # - 'Material' (engineering material classification)
    # - 'CreatedOn' / 'ModifiedOn' (timestamps)

    Args:
        raw: Dictionary representing a PTC.ProdMgmt.Part OData entity.

    Returns:
        Normalized Part model instance.
    """
    part_number = str(raw.get("Number") or raw.get("part_number") or raw.get("ID") or "").strip()
    name = str(raw.get("Name") or raw.get("name") or part_number).strip()
    revision, iteration, version_label = map_windchill_version(raw)
    lifecycle_state = map_windchill_state(raw.get("State") or raw.get("LifeCycleState"))
    description = str(raw.get("Description") or raw.get("description") or "").strip()
    make_buy = map_windchill_make_buy(raw.get("Source") or raw.get("make_buy"))
    material = str(raw.get("Material") or raw.get("material") or "").strip()

    created_at = parse_windchill_timestamp(raw.get("CreatedOn") or raw.get("created_at"))
    updated_at = parse_windchill_timestamp(raw.get("ModifiedOn") or raw.get("updated_at") or raw.get("CreatedOn"))

    return Part(
        part_number=part_number,
        name=name,
        revision=revision,
        iteration=iteration,
        version_label=version_label,
        lifecycle_state=lifecycle_state,
        description=description,
        make_buy=make_buy,
        material=material,
        created_at=created_at,
        updated_at=updated_at,
    )


def map_windchill_parts_to_normalized(raw_list: list[dict[str, Any]]) -> list[Part]:
    """Map a list of raw Windchill Part entities to a list of normalized Part models.

    Args:
        raw_list: List of raw OData part entities.

    Returns:
        List of normalized Part models.
    """
    return [map_windchill_part_to_normalized(raw) for raw in raw_list if raw]


def map_windchill_bom_link_to_normalized(
    parent_part_number: str,
    raw_usage: dict[str, Any],
    level: int = 1,
) -> BomLink:
    """Map a raw Windchill PartStructure or UsageLink entity to normalized BomLink.

    # TODO: verify against Windchill docs / $metadata:
    # In WRS, PartStructure navigation returns components with:
    # - 'Quantity': {'Value': 2.0, 'Unit': 'ea'} or float 2.0
    # - 'FindNumber': int or string find number / balloon line
    # - 'ReferenceDesignator': string or null
    # - 'Part' or 'ChildPart': nested expanded child part entity

    Args:
        parent_part_number: Parent assembly part number.
        raw_usage: Dictionary representing the usage link / component association.
        level: Current depth in hierarchy (default 1).

    Returns:
        Normalized BomLink instance.
    """
    # Extract child entity (could be under 'Part', 'ChildPart', or top-level)
    child_entity = raw_usage.get("Part") or raw_usage.get("ChildPart") or {}
    child_part_number = str(
        child_entity.get("Number")
        or raw_usage.get("ChildPartNumber")
        or raw_usage.get("Number")
        or ""
    ).strip()

    child_name = str(
        child_entity.get("Name")
        or raw_usage.get("ChildName")
        or raw_usage.get("Name")
        or ""
    ).strip()

    # Extract quantity and unit
    qty_raw = raw_usage.get("Quantity")
    if isinstance(qty_raw, dict):
        try:
            quantity = float(qty_raw.get("Value", 1.0))
        except (ValueError, TypeError):
            quantity = 1.0
        unit = str(qty_raw.get("Unit") or "ea").strip()
    elif qty_raw is not None:
        try:
            quantity = float(qty_raw)
        except (ValueError, TypeError):
            quantity = 1.0
        unit = str(raw_usage.get("Unit") or "ea").strip()
    else:
        quantity = 1.0
        unit = "ea"

    # Extract find number
    fn_raw = raw_usage.get("FindNumber") or raw_usage.get("LineNumber")
    try:
        find_number = int(fn_raw) if fn_raw is not None else None
    except (ValueError, TypeError):
        find_number = None

    ref_des = raw_usage.get("ReferenceDesignator") or raw_usage.get("RefDesignator")
    bom_type = str(raw_usage.get("BOMType") or "EBOM").strip().upper()
    notes = str(raw_usage.get("Notes") or raw_usage.get("UsageNotes") or "").strip()

    return BomLink(
        parent_part_number=parent_part_number,
        child_part_number=child_part_number,
        child_name=child_name,
        quantity=quantity,
        unit=unit,
        find_number=find_number,
        ref_designators=ref_des,
        level=level,
        bom_type=bom_type,
        notes=notes,
    )


def map_windchill_bom_structure_to_normalized(
    parent_part_number: str,
    raw_structure: list[dict[str, Any]] | dict[str, Any],
    level: int = 1,
) -> list[BomLink]:
    """Map raw Windchill BOM explosion / PartStructure to list of normalized BomLinks.

    # TODO: verify against Windchill docs / $metadata:
    # WRS can return PartStructure as a list or wrapped in an OData response {'value': [...]}.
    # If $expand is used recursively, child items may contain their own 'PartStructure'.

    Args:
        parent_part_number: Parent assembly part number.
        raw_structure: OData response array or dict with 'value' list.
        level: Current BOM depth.

    Returns:
        List of normalized BomLink objects.
    """
    items = raw_structure.get("value", []) if isinstance(raw_structure, dict) else raw_structure
    if not isinstance(items, list):
        return []

    bom_links: list[BomLink] = []
    for raw_item in items:
        if not raw_item:
            continue
        link = map_windchill_bom_link_to_normalized(
            parent_part_number=parent_part_number,
            raw_usage=raw_item,
            level=level,
        )
        bom_links.append(link)

        # Check for nested sub-assemblies if multi-level $expand was performed
        child_entity = raw_item.get("Part") or raw_item.get("ChildPart") or {}
        sub_structure = child_entity.get("PartStructure") or raw_item.get("PartStructure")
        if sub_structure:
            sub_links = map_windchill_bom_structure_to_normalized(
                parent_part_number=link.child_part_number,
                raw_structure=sub_structure,
                level=level + 1,
            )
            bom_links.extend(sub_links)

    return bom_links

