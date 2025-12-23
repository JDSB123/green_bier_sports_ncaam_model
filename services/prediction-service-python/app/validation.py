"""
Data validation utilities for NCAA Basketball Prediction Service.

Validates odds, ratings, and other input data to prevent garbage-in issues.
Invalid data is flagged/rejected before it corrupts predictions.
"""

import structlog
from dataclasses import dataclass
from typing import Optional, List, Tuple
from enum import Enum


logger = structlog.get_logger()


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""
    WARNING = "warning"   # Log but continue
    ERROR = "error"       # Skip this item
    CRITICAL = "critical" # Abort entire operation


@dataclass
class ValidationIssue:
    """A single validation issue."""
    field: str
    value: any
    message: str
    severity: ValidationSeverity


@dataclass 
class ValidationResult:
    """Result of validation with all issues found."""
    is_valid: bool
    issues: List[ValidationIssue]
    
    @property
    def has_errors(self) -> bool:
        return any(i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL) for i in self.issues)
    
    @property
    def has_warnings(self) -> bool:
        return any(i.severity == ValidationSeverity.WARNING for i in self.issues)
    
    def log_issues(self, context: str = ""):
        """Log all validation issues."""
        for issue in self.issues:
            log_method = logger.warning if issue.severity == ValidationSeverity.WARNING else logger.error
            log_method(
                f"Validation {issue.severity.value}",
                context=context,
                field=issue.field,
                value=issue.value,
                message=issue.message,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# ODDS VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

# Valid ranges for odds data
SPREAD_MIN = -50.0   # Max point spread (no team is 50+ point favorite)
SPREAD_MAX = 50.0
TOTAL_MIN = 80.0     # Minimum plausible total
TOTAL_MAX = 220.0    # Maximum plausible total (high tempo + OT possible)
PRICE_MIN = -300     # Standard juice range
PRICE_MAX = -100     # Standard juice range (worse than -300 is suspicious)


def validate_spread(
    spread: Optional[float],
    field_name: str = "spread",
) -> List[ValidationIssue]:
    """Validate a spread value is within plausible bounds."""
    issues = []
    
    if spread is None:
        return issues  # None is valid (no odds available)
    
    if not isinstance(spread, (int, float)):
        issues.append(ValidationIssue(
            field=field_name,
            value=spread,
            message=f"Spread must be numeric, got {type(spread).__name__}",
            severity=ValidationSeverity.ERROR,
        ))
        return issues
    
    if spread < SPREAD_MIN or spread > SPREAD_MAX:
        issues.append(ValidationIssue(
            field=field_name,
            value=spread,
            message=f"Spread {spread} outside valid range [{SPREAD_MIN}, {SPREAD_MAX}]",
            severity=ValidationSeverity.ERROR,
        ))
    
    # Very large spreads are unusual but possible (warn only)
    if abs(spread) > 35:
        issues.append(ValidationIssue(
            field=field_name,
            value=spread,
            message=f"Unusually large spread {spread} (> 35 points)",
            severity=ValidationSeverity.WARNING,
        ))
    
    return issues


def validate_total(
    total: Optional[float],
    field_name: str = "total",
) -> List[ValidationIssue]:
    """Validate a total value is within plausible bounds."""
    issues = []
    
    if total is None:
        return issues
    
    if not isinstance(total, (int, float)):
        issues.append(ValidationIssue(
            field=field_name,
            value=total,
            message=f"Total must be numeric, got {type(total).__name__}",
            severity=ValidationSeverity.ERROR,
        ))
        return issues
    
    if total < TOTAL_MIN:
        issues.append(ValidationIssue(
            field=field_name,
            value=total,
            message=f"Total {total} below minimum {TOTAL_MIN} (impossibly low)",
            severity=ValidationSeverity.ERROR,
        ))
    
    if total > TOTAL_MAX:
        issues.append(ValidationIssue(
            field=field_name,
            value=total,
            message=f"Total {total} above maximum {TOTAL_MAX} (impossibly high)",
            severity=ValidationSeverity.ERROR,
        ))
    
    # Very high/low totals are unusual but possible
    if total < 110 or total > 180:
        issues.append(ValidationIssue(
            field=field_name,
            value=total,
            message=f"Unusual total {total} (typical range: 110-180)",
            severity=ValidationSeverity.WARNING,
        ))
    
    return issues


# First half total bounds (roughly 45-52% of full game)
TOTAL_1H_MIN = 40.0    # Minimum plausible 1H total
TOTAL_1H_MAX = 110.0   # Maximum plausible 1H total


def validate_total_1h(
    total: Optional[float],
    field_name: str = "total_1h",
) -> List[ValidationIssue]:
    """Validate a first half total value is within plausible bounds."""
    issues = []
    
    if total is None:
        return issues
    
    if not isinstance(total, (int, float)):
        issues.append(ValidationIssue(
            field=field_name,
            value=total,
            message=f"Total must be numeric, got {type(total).__name__}",
            severity=ValidationSeverity.ERROR,
        ))
        return issues
    
    if total < TOTAL_1H_MIN:
        issues.append(ValidationIssue(
            field=field_name,
            value=total,
            message=f"1H Total {total} below minimum {TOTAL_1H_MIN} (impossibly low)",
            severity=ValidationSeverity.ERROR,
        ))
    
    if total > TOTAL_1H_MAX:
        issues.append(ValidationIssue(
            field=field_name,
            value=total,
            message=f"1H Total {total} above maximum {TOTAL_1H_MAX} (impossibly high)",
            severity=ValidationSeverity.ERROR,
        ))
    
    # Very high/low 1H totals are unusual but possible
    if total < 55 or total > 90:
        issues.append(ValidationIssue(
            field=field_name,
            value=total,
            message=f"Unusual 1H total {total} (typical range: 55-90)",
            severity=ValidationSeverity.WARNING,
        ))
    
    return issues





def validate_price(
    price: Optional[int],
    field_name: str = "price",
) -> List[ValidationIssue]:
    """Validate a juice/price value (should typically be around -110)."""
    issues = []
    
    if price is None:
        return issues
    
    if not isinstance(price, (int, float)):
        issues.append(ValidationIssue(
            field=field_name,
            value=price,
            message=f"Price must be numeric, got {type(price).__name__}",
            severity=ValidationSeverity.ERROR,
        ))
        return issues
    
    price = int(price)
    
    # Most prices should be negative (standard is -110)
    if price > 0:
        issues.append(ValidationIssue(
            field=field_name,
            value=price,
            message=f"Positive price {price} is unusual for spread/total (expect negative juice)",
            severity=ValidationSeverity.WARNING,
        ))
    
    # Extremely high juice is suspicious
    if price < -250:
        issues.append(ValidationIssue(
            field=field_name,
            value=price,
            message=f"Extremely high juice {price} (> -250)",
            severity=ValidationSeverity.WARNING,
        ))
    
    return issues


def validate_market_odds(
    spread: Optional[float] = None,
    total: Optional[float] = None,
    spread_1h: Optional[float] = None,
    total_1h: Optional[float] = None,
    spread_price: Optional[int] = None,
    over_price: Optional[int] = None,
    context: str = "",
) -> ValidationResult:
    """
    Validate complete market odds data.
    
    Returns ValidationResult with all issues found.
    """
    issues = []
    
    # Full game odds
    issues.extend(validate_spread(spread, "spread"))
    issues.extend(validate_total(total, "total"))
    issues.extend(validate_price(spread_price, "spread_price"))
    issues.extend(validate_price(over_price, "over_price"))
    
    # First half odds - use different bounds
    issues.extend(validate_spread(spread_1h, "spread_1h"))
    issues.extend(validate_total_1h(total_1h, "total_1h"))
    
    # Cross-field validation
    
    # 1H spread should be smaller magnitude than FG spread
    if spread is not None and spread_1h is not None:
        if abs(spread_1h) > abs(spread):
            issues.append(ValidationIssue(
                field="spread_1h",
                value=spread_1h,
                message=f"1H spread ({spread_1h}) larger than FG spread ({spread})",
                severity=ValidationSeverity.WARNING,
            ))
    
    # 1H total should be less than FG total
    if total is not None and total_1h is not None:
        if total_1h >= total:
            issues.append(ValidationIssue(
                field="total_1h",
                value=total_1h,
                message=f"1H total ({total_1h}) >= FG total ({total})",
                severity=ValidationSeverity.ERROR,
            ))
        elif total_1h / total > 0.55:
            issues.append(ValidationIssue(
                field="total_1h",
                value=total_1h,
                message=f"1H total ({total_1h}) is > 55% of FG total ({total})",
                severity=ValidationSeverity.WARNING,
            ))
    
    
    is_valid = not any(i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL) for i in issues)
    result = ValidationResult(is_valid=is_valid, issues=issues)
    
    if issues and context:
        result.log_issues(context)
    
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# RATINGS VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

# Valid ranges for Barttorvik ratings
EFFICIENCY_MIN = 70.0   # Worst D1 team still scores/allows ~70/100 poss
EFFICIENCY_MAX = 140.0  # Best teams rarely exceed 130
TEMPO_MIN = 55.0        # Slowest pace
TEMPO_MAX = 85.0        # Fastest pace
EFG_MIN = 30.0          # Minimum plausible EFG%
EFG_MAX = 70.0          # Maximum plausible EFG%
RATE_MIN = 0.0          # Minimum rate (0%)
RATE_MAX = 100.0        # Maximum rate (100%)


def validate_efficiency(
    value: Optional[float],
    field_name: str,
) -> List[ValidationIssue]:
    """Validate an efficiency rating (AdjO/AdjD)."""
    issues = []
    
    if value is None:
        issues.append(ValidationIssue(
            field=field_name,
            value=value,
            message=f"{field_name} is required but was None",
            severity=ValidationSeverity.ERROR,
        ))
        return issues
    
    if value < EFFICIENCY_MIN or value > EFFICIENCY_MAX:
        issues.append(ValidationIssue(
            field=field_name,
            value=value,
            message=f"{field_name} {value} outside valid range [{EFFICIENCY_MIN}, {EFFICIENCY_MAX}]",
            severity=ValidationSeverity.ERROR,
        ))
    
    return issues


def validate_tempo(
    tempo: Optional[float],
    field_name: str = "tempo",
) -> List[ValidationIssue]:
    """Validate tempo rating."""
    issues = []
    
    if tempo is None:
        issues.append(ValidationIssue(
            field=field_name,
            value=tempo,
            message="Tempo is required but was None",
            severity=ValidationSeverity.ERROR,
        ))
        return issues
    
    if tempo < TEMPO_MIN or tempo > TEMPO_MAX:
        issues.append(ValidationIssue(
            field=field_name,
            value=tempo,
            message=f"Tempo {tempo} outside valid range [{TEMPO_MIN}, {TEMPO_MAX}]",
            severity=ValidationSeverity.ERROR,
        ))
    
    return issues


def validate_percentage(
    value: Optional[float],
    field_name: str,
    min_val: float = RATE_MIN,
    max_val: float = RATE_MAX,
) -> List[ValidationIssue]:
    """Validate a percentage/rate value."""
    issues = []
    
    if value is None:
        issues.append(ValidationIssue(
            field=field_name,
            value=value,
            message=f"{field_name} is required but was None",
            severity=ValidationSeverity.ERROR,
        ))
        return issues
    
    if value < min_val or value > max_val:
        issues.append(ValidationIssue(
            field=field_name,
            value=value,
            message=f"{field_name} {value} outside valid range [{min_val}, {max_val}]",
            severity=ValidationSeverity.ERROR,
        ))
    
    return issues


def validate_team_ratings(
    adj_o: Optional[float],
    adj_d: Optional[float],
    tempo: Optional[float],
    efg: Optional[float],
    efgd: Optional[float],
    tor: Optional[float],
    tord: Optional[float],
    orb: Optional[float],
    drb: Optional[float],
    team_name: str = "",
) -> ValidationResult:
    """
    Validate complete team ratings data.
    
    Returns ValidationResult with all issues found.
    """
    issues = []
    
    # Core efficiency metrics
    issues.extend(validate_efficiency(adj_o, "adj_o"))
    issues.extend(validate_efficiency(adj_d, "adj_d"))
    issues.extend(validate_tempo(tempo))
    
    # Four Factors
    issues.extend(validate_percentage(efg, "efg", EFG_MIN, EFG_MAX))
    issues.extend(validate_percentage(efgd, "efgd", EFG_MIN, EFG_MAX))
    issues.extend(validate_percentage(tor, "tor", 5.0, 35.0))
    issues.extend(validate_percentage(tord, "tord", 5.0, 35.0))
    issues.extend(validate_percentage(orb, "orb", 10.0, 50.0))
    issues.extend(validate_percentage(drb, "drb", 50.0, 90.0))
    
    # Cross-field validation
    if adj_o is not None and adj_d is not None:
        net = adj_o - adj_d
        if net > 50:
            issues.append(ValidationIssue(
                field="net_rating",
                value=net,
                message=f"Net rating {net} is impossibly high",
                severity=ValidationSeverity.ERROR,
            ))
        if net < -50:
            issues.append(ValidationIssue(
                field="net_rating",
                value=net,
                message=f"Net rating {net} is impossibly low",
                severity=ValidationSeverity.ERROR,
            ))
    
    is_valid = not any(i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL) for i in issues)
    result = ValidationResult(is_valid=is_valid, issues=issues)
    
    if issues and team_name:
        result.log_issues(f"team={team_name}")
    
    return result

