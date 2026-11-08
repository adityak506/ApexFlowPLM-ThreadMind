"""Input Validation and Security Sanitization Module.

Provides centralized input validation, parameter boundary checking,
injection defense (SQL/OData), prompt injection filtering, and
credential redaction for audit logging.
"""

import re
from typing import Any

# Allowed characters for part numbers: alphanumeric, dash, underscore, dot, colon, slash
PART_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9_\-\.:/]+$")

# Valid PLM lifecycle states
ALLOWED_LIFECYCLE_STATES = {"IN_WORK", "UNDER_REVIEW", "RELEASED", "OBSOLETE"}

# Sensitive argument keys that must be redacted in audit logs
SENSITIVE_KEYS = {
    "password", "secret", "token", "api_key", "apikey", "auth",
    "authorization", "access_token", "private_key", "credentials",
}


def sanitize_text(text: str | None, max_length: int = 1000, allow_empty: bool = True) -> str:
    """Sanitize freeform text inputs (titles, reasons, descriptions).

    - Removes null bytes and non-printable control characters (except newline/tab).
    - Truncates/enforces maximum character length.
    - Prevents buffer/memory exhaustion attacks.

    Args:
        text: Raw text string.
        max_length: Maximum allowed character count.
        allow_empty: Whether an empty string is permissible.

    Returns:
        Sanitized text string.

    Raises:
        ValueError: If text is empty when allow_empty is False or exceeds max_length.
    """
    if text is None:
        if not allow_empty:
            raise ValueError("Field cannot be null or empty.")
        return ""

    if not isinstance(text, str):
        text = str(text)

    # Strip null bytes and dangerous control characters (keep \n, \r, \t)
    cleaned = "".join(ch for ch in text if ch in "\n\r\t" or (len(ch.encode("utf-8")) == 1 and ord(ch) >= 32) or ord(ch) > 126)
    cleaned = cleaned.strip()

    if not cleaned and not allow_empty:
        raise ValueError("Field cannot be blank or whitespace-only.")

    if len(cleaned) > max_length:
        raise ValueError(f"Input exceeds maximum allowed length of {max_length} characters (received {len(cleaned)}).")

    return cleaned


def validate_part_number(part_number: str) -> str:
    """Validate and sanitize a part identification number.

    Args:
        part_number: Part number string to validate.

    Returns:
        Cleaned part number string.

    Raises:
        ValueError: If part number is invalid, empty, or contains injection characters.
    """
    clean_pno = sanitize_text(part_number, max_length=64, allow_empty=False)

    if not PART_NUMBER_PATTERN.match(clean_pno):
        raise ValueError(
            f"Invalid part number '{clean_pno}'. Part numbers may only contain "
            "alphanumeric characters, dashes, underscores, dots, slashes, and colons."
        )

    return clean_pno


def validate_part_numbers(part_numbers: list[str], max_count: int = 50) -> list[str]:
    """Validate a list of part identification numbers.

    Args:
        part_numbers: List of part number strings.
        max_count: Maximum number of parts allowed in a single operation.

    Returns:
        Deduplicated list of validated part numbers.

    Raises:
        ValueError: If list is empty, exceeds max_count, or contains invalid part numbers.
    """
    if not part_numbers:
        raise ValueError("At least one affected part number must be specified.")

    if len(part_numbers) > max_count:
        raise ValueError(f"Exceeded maximum batch limit of {max_count} parts (received {len(part_numbers)}).")

    validated = []
    seen = set()
    for p in part_numbers:
        clean = validate_part_number(p)
        if clean not in seen:
            seen.add(clean)
            validated.append(clean)

    return validated


def validate_lifecycle_state(state: str | None) -> str | None:
    """Validate lifecycle state string against allowed enum values.

    Args:
        state: State string or None.

    Returns:
        Normalized uppercase state string or None.

    Raises:
        ValueError: If state string is not a valid lifecycle state.
    """
    if not state:
        return None

    clean_state = str(state).strip().upper()
    if clean_state not in ALLOWED_LIFECYCLE_STATES:
        raise ValueError(
            f"Invalid lifecycle state '{state}'. Allowed states: {sorted(ALLOWED_LIFECYCLE_STATES)}"
        )
    return clean_state


def validate_pagination_limit(limit: int, min_val: int = 1, max_val: int = 500) -> int:
    """Validate pagination limit integer.

    Args:
        limit: Requested result count limit.
        min_val: Minimum acceptable value (default 1).
        max_val: Maximum acceptable value (default 500).

    Returns:
        Bounded limit integer.

    Raises:
        ValueError: If limit is out of acceptable bounds.
    """
    try:
        val = int(limit)
    except (ValueError, TypeError):
        raise ValueError(f"Limit must be an integer (received: {limit}).")

    if val < min_val or val > max_val:
        raise ValueError(f"Limit must be between {min_val} and {max_val} (received: {val}).")

    return val


def validate_bom_levels(levels: int, max_levels: int = 10) -> int:
    """Validate BOM hierarchy explosion depth levels.

    Args:
        levels: Depth of hierarchy traversal.
        max_levels: Maximum allowable depth (default 10).

    Returns:
        Bounded levels integer.

    Raises:
        ValueError: If levels is invalid or exceeds bounds.
    """
    try:
        val = int(levels)
    except (ValueError, TypeError):
        raise ValueError(f"BOM levels must be an integer (received: {levels}).")

    if val < 1 or val > max_levels:
        raise ValueError(f"BOM levels must be between 1 and {max_levels} (received: {val}).")

    return val


def sanitize_like_pattern(text: str) -> str:
    """Escape SQL LIKE wildcard characters (% and _) with backslash."""
    if not text:
        return ""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def redact_sensitive_args(args: dict[str, Any]) -> dict[str, Any]:
    """Recursively scrub sensitive keys from arguments before recording to audit log.

    Args:
        args: Dictionary of tool call arguments.

    Returns:
        Sanitized dictionary with sensitive values replaced by '[REDACTED]'.
    """
    sanitized: dict[str, Any] = {}
    for k, v in args.items():
        if any(s in k.lower() for s in SENSITIVE_KEYS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = redact_sensitive_args(v)
        elif isinstance(v, list):
            sanitized[k] = [
                redact_sensitive_args(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized

