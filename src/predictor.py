"""
Republication prediction for government tenders.
Predicts when tenders will be re-published based on contract duration assumptions.
"""

import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Optional

from .config import (
    DEFAULT_CONTRACT_YEARS,
    DEFAULT_LEAD_MONTHS,
    PRIORITY_THRESHOLDS,
)


def get_seasonal_pattern(dates: list) -> Optional[str]:
    """
    Detect seasonal publication pattern from a list of publication dates.

    If an organization published multiple times, find the most common quarter.
    Returns a string like "Publiceert meestal in Q4" if a pattern is detected,
    or None if there aren't enough dates or no clear pattern.

    Requires at least 2 dates, and the most common quarter must appear
    in more than half of the publications.
    """
    if not dates or len(dates) < 2:
        return None

    # Get quarter numbers (1-4) for each date
    quarters = []
    for d in dates:
        if pd.notna(d):
            q = (d.month - 1) // 3 + 1
            quarters.append(q)

    if len(quarters) < 2:
        return None

    # Find most common quarter
    from collections import Counter
    counter = Counter(quarters)
    most_common_q, most_common_count = counter.most_common(1)[0]

    # Pattern exists if the most common quarter appears in more than half
    if most_common_count > len(quarters) / 2:
        return f"Publiceert meestal in Q{most_common_q}"

    return None


def get_reference_date(row: pd.Series) -> tuple[Optional[datetime], str]:
    """
    Determine the best reference date for prediction.

    BELANGRIJKE LOGICA (gebaseerd op input Tom Bos):
    Overheidsorganisaties werken met budgetcycli. Als ze in november publiceerden,
    zullen ze weer in november publiceren - niet gebaseerd op gunningsdatum.

    Priority:
    1. contract_end - Exacte einddatum bekend, geen schatting nodig
    2. publication_date - Budgetcyclus bepaalt wanneer opnieuw gepubliceerd wordt
    3. contract_start - Fallback als niets anders beschikbaar

    Returns:
        Tuple of (reference_date, reference_type)
        reference_type indicates whether we need to add contract_years or not:
        - "contract_end": Use date directly (no years to add)
        - "publication_date": Add contract_years for republication estimate
        - "contract_start": Add contract_years for republication estimate
    """
    # Best: exact contract end date known
    if "contract_end" in row.index and pd.notna(row.get("contract_end")):
        return row["contract_end"], "contract_end"

    # Good: publication date (matches budget cycles)
    if "publication_date" in row.index and pd.notna(row.get("publication_date")):
        return row["publication_date"], "publication_date"

    # Fallback: contract start date
    if "contract_start" in row.index and pd.notna(row.get("contract_start")):
        return row["contract_start"], "contract_start"

    return None, ""


def calculate_expected_republication(
    reference_date: datetime,
    contract_years: int = DEFAULT_CONTRACT_YEARS,
) -> datetime:
    """
    Calculate expected republication date based on reference date and contract duration.
    """
    return reference_date + relativedelta(years=contract_years)


def calculate_contact_date(
    republication_date: datetime,
    lead_months: int = DEFAULT_LEAD_MONTHS,
) -> datetime:
    """
    Calculate when sales should contact the organization.
    This is lead_months before the expected republication.
    """
    return republication_date - relativedelta(months=lead_months)


def assign_priority(days_until_contact: Optional[int]) -> str:
    """
    Assign priority level based on days until contact is needed.
    """
    if days_until_contact is None:
        return "UNKNOWN"

    if days_until_contact < 0:
        return "OVERDUE"

    for priority, threshold in PRIORITY_THRESHOLDS.items():
        if days_until_contact <= threshold:
            return priority

    return "LOW"


def calculate_confidence_score(row: pd.Series) -> int:
    """
    Calculate confidence score for the prediction (0-100).
    Higher score = more reliable prediction.

    Scoring gebaseerd op nieuwe prioriteiten:
    - contract_end is meest betrouwbaar (exacte einddatum)
    - publication_date is goed (budgetcyclus logica)
    - contract_start is fallback
    """
    score = 0

    # Best: has actual contract end date (most reliable prediction)
    if "contract_end" in row.index and pd.notna(row.get("contract_end")):
        score += 40

    # Good: has publication date (budget cycle logic)
    if "publication_date" in row.index and pd.notna(row.get("publication_date")):
        score += 25

    # Okay: has contract start date (fallback)
    elif "contract_start" in row.index and pd.notna(row.get("contract_start")):
        score += 15

    # Has contract value (larger contracts more likely to repeat)
    if "contract_value" in row.index and pd.notna(row.get("contract_value")):
        value = row.get("contract_value", 0)
        if value > 100000:
            score += 20
        elif value > 50000:
            score += 15
        elif value > 10000:
            score += 10

    # Has description (more complete data)
    if "description" in row.index and len(str(row.get("description", ""))) > 100:
        score += 10

    # CPV code match (relevant category)
    if "matched_cpv" in row.index and row.get("matched_cpv"):
        score += 5

    return min(score, 100)


def predict_republication_dates(
    df: pd.DataFrame,
    contract_years: int = DEFAULT_CONTRACT_YEARS,
    lead_months: int = DEFAULT_LEAD_MONTHS,
) -> pd.DataFrame:
    """
    Add republication predictions to tender data.

    Args:
        df: DataFrame with relevant tenders
        contract_years: Assumed contract duration in years
        lead_months: Months before republication to contact

    Returns:
        DataFrame with prediction columns added:
        - reference_date: Date used as basis for prediction
        - expected_republication: Predicted republication date
        - contact_by_date: When to contact the organization
        - days_until_contact: Days from today until contact needed
        - priority: URGENT/HIGH/MEDIUM/LOW/OVERDUE/UNKNOWN
        - confidence_score: 0-100 reliability score
    """
    result = df.copy()
    today = datetime.now()

    # Initialize new columns
    result["reference_date"] = None
    result["reference_type"] = ""
    result["expected_republication"] = None
    result["republication_basis"] = ""
    result["contact_by_date"] = None
    result["days_until_contact"] = None
    result["priority"] = "UNKNOWN"
    result["confidence_score"] = 0

    for idx, row in result.iterrows():
        # Get reference date and type
        ref_date, ref_type_key = get_reference_date(row)

        if ref_date is None:
            continue

        # Determine display label and explanation for reference type
        if ref_type_key == "contract_end":
            ref_type = "Einddatum contract"
            republication = ref_date
            explanation = f"Einddatum contract: {ref_date.strftime('%Y-%m-%d')}"
        elif ref_type_key == "publication_date":
            ref_type = "Publicatiedatum"
            republication = calculate_expected_republication(ref_date, contract_years)
            explanation = f"Publicatiedatum {ref_date.strftime('%Y-%m-%d')} + {contract_years} jaar contractduur"
        else:  # contract_start
            ref_type = "Startdatum contract"
            republication = calculate_expected_republication(ref_date, contract_years)
            explanation = f"Startdatum contract {ref_date.strftime('%Y-%m-%d')} + {contract_years} jaar contractduur"

        # Calculate contact date (lead_months before republication)
        contact_date = calculate_contact_date(republication, lead_months)

        # Calculate days until contact
        days_until = (contact_date - today).days

        # Assign priority
        priority = assign_priority(days_until)

        # Calculate confidence
        confidence = calculate_confidence_score(row)

        # Update row
        result.at[idx, "reference_date"] = ref_date
        result.at[idx, "reference_type"] = ref_type
        result.at[idx, "expected_republication"] = republication
        result.at[idx, "republication_basis"] = explanation
        result.at[idx, "contact_by_date"] = contact_date
        result.at[idx, "days_until_contact"] = days_until
        result.at[idx, "priority"] = priority
        result.at[idx, "confidence_score"] = confidence

    return result


def get_actionable_tenders(
    df: pd.DataFrame,
    max_days: int = 180,
    min_confidence: int = 0,
) -> pd.DataFrame:
    """
    Get tenders that need action within the specified timeframe.

    Args:
        df: DataFrame with predictions
        max_days: Maximum days until contact (default: 180 = 6 months)
        min_confidence: Minimum confidence score to include

    Returns:
        Filtered and sorted DataFrame
    """
    # Filter by timeframe and confidence
    mask = (
        (df["days_until_contact"].notna())
        & (df["days_until_contact"] <= max_days)
        & (df["confidence_score"] >= min_confidence)
    )

    result = df[mask].copy()

    # Sort by days until contact (most urgent first)
    result = result.sort_values("days_until_contact", ascending=True)

    return result


def get_priority_summary(df: pd.DataFrame) -> dict:
    """
    Get summary counts by priority level.
    """
    priority_counts = df["priority"].value_counts().to_dict()

    # Ensure all priorities are present
    for priority in ["OVERDUE", "URGENT", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]:
        if priority not in priority_counts:
            priority_counts[priority] = 0

    return priority_counts


def get_monthly_forecast(df: pd.DataFrame, months_ahead: int = 12) -> pd.DataFrame:
    """
    Get forecast of contacts needed per month.
    """
    today = datetime.now()

    # Filter to valid contact dates
    valid_df = df[df["contact_by_date"].notna()].copy()

    # Create month periods
    valid_df["contact_month"] = valid_df["contact_by_date"].dt.to_period("M")

    # Count per month
    monthly_counts = valid_df.groupby("contact_month").size().reset_index(name="count")

    # Filter to future months
    current_period = pd.Period(today, freq="M")
    future_period = pd.Period(today + relativedelta(months=months_ahead), freq="M")

    monthly_counts = monthly_counts[
        (monthly_counts["contact_month"] >= current_period)
        & (monthly_counts["contact_month"] <= future_period)
    ]

    # Convert period to string for display
    monthly_counts["month_label"] = monthly_counts["contact_month"].astype(str)

    return monthly_counts
