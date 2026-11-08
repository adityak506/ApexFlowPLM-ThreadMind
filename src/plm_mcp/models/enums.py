"""Domain enumerations for the Windchill-style PLM system."""

from enum import Enum


class LifecycleState(str, Enum):
    """PLM lifecycle states following Windchill conventions."""

    IN_WORK = "IN_WORK"
    UNDER_REVIEW = "UNDER_REVIEW"
    RELEASED = "RELEASED"
    OBSOLETE = "OBSOLETE"


class DocType(str, Enum):
    """Document classification types."""

    SPECIFICATION = "SPECIFICATION"
    CAD_DRAWING = "CAD_DRAWING"
    TEST_REPORT = "TEST_REPORT"
    USER_MANUAL = "USER_MANUAL"


class PartDocLinkType(str, Enum):
    """Association type between parts and documents."""

    DESCRIBES = "DESCRIBES"
    REFERENCES = "REFERENCES"


class ChangeCategory(str, Enum):
    """Category classification for Change Requests."""

    DESIGN_IMPROVEMENT = "DESIGN_IMPROVEMENT"
    DEFECT = "DEFECT"
    COST_REDUCTION = "COST_REDUCTION"
    COMPLIANCE = "COMPLIANCE"


class ChangePriority(str, Enum):
    """Priority levels for change management."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EMERGENCY = "EMERGENCY"


class ChangeRequestState(str, Enum):
    """Lifecycle states for Change Requests (ECR)."""

    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"


class ChangeNoticeState(str, Enum):
    """Lifecycle states for Change Notices (ECN)."""

    OPEN = "OPEN"
    IN_WORK = "IN_WORK"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ItemDisposition(str, Enum):
    """Material disposition directives on Change Notices."""

    SCRAP = "SCRAP"
    REWORK = "REWORK"
    USE_AS_IS = "USE_AS_IS"


class SourcingStatus(str, Enum):
    """AML/AVL approval status for external manufacturer parts."""

    PREFERRED = "PREFERRED"
    APPROVED = "APPROVED"
    DO_NOT_USE = "DO_NOT_USE"
    UNDER_REVIEW = "UNDER_REVIEW"


class ManufacturerStatus(str, Enum):
    """Manufacturer/vendor operating status."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    RESTRICTED = "RESTRICTED"

