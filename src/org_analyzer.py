"""
Organization-level analysis for SkillsTown TenderNed Analyzer.
Groups tenders by organization to create an analysis overview.
"""

import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Optional

from .config import DEFAULT_CONTRACT_YEARS, DEFAULT_LEAD_MONTHS
from .predictor import get_seasonal_pattern


def get_quarter_label(date: datetime) -> str:
    """Convert a date to quarter label (Q1/Q2/Q3/Q4 + year)."""
    if pd.isna(date):
        return ""
    quarter = (date.month - 1) // 3 + 1
    return f"Q{quarter} {date.year}"


def get_quarter_sort_key(quarter_label: str) -> int:
    """Get sort key for quarter labels (e.g., 'Q1 2026' -> 20261)."""
    if not quarter_label:
        return 999999
    try:
        parts = quarter_label.split()
        quarter = int(parts[0][1])
        year = int(parts[1])
        return year * 10 + quarter
    except (IndexError, ValueError):
        return 999999


def aggregate_organizations(
    df: pd.DataFrame,
    contract_years: int = DEFAULT_CONTRACT_YEARS,
    lead_months: int = DEFAULT_LEAD_MONTHS,
) -> pd.DataFrame:
    """
    Aggregate tenders by organization for analysis overview.

    Returns DataFrame with one row per organization containing:
    - organization, city
    - last_publication_date, years_since_publication
    - expected_republication, expected_republication_quarter
    - contact_quarter, days_until_contact
    - priority
    - competitors_won
    - total_contract_value
    - tender_count, tender_titles
    - publication_pattern
    """
    if df.empty:
        return pd.DataFrame()

    today = datetime.now()
    org_groups = df.groupby("organization", dropna=False)
    org_data = []

    for org_name, group in org_groups:
        if pd.isna(org_name) or str(org_name).strip() == "":
            continue

        # --- Determine most relevant tender per organization ---
        # Rank: keyword+cpv (3) > keyword (2) > cpv (1) > none (0)
        # Within same rank: most recent publication wins
        match_rank = {"keyword+cpv": 3, "keyword": 2, "cpv": 1}

        def _tender_sort_key(idx):
            row = group.loc[idx]
            mt = str(row.get("match_type", "")).lower() if "match_type" in group.columns else ""
            rank = 0
            for key, val in match_rank.items():
                if key in mt:
                    rank = max(rank, val)
            pub = row.get("publication_date")
            pub_ts = pub.timestamp() if pd.notna(pub) else 0
            return (rank, pub_ts)

        best_idx = max(group.index, key=_tender_sort_key)
        best_tender = group.loc[best_idx]

        # City (most common)
        city = ""
        if "organization_city" in group.columns:
            cities = group["organization_city"].dropna()
            if len(cities) > 0:
                city = cities.mode().iloc[0] if len(cities.mode()) > 0 else cities.iloc[0]

        # Most recent publication date (from all tenders, for context)
        pub_dates = group["publication_date"].dropna()
        if len(pub_dates) > 0:
            last_pub_date = pub_dates.max()
            years_since = round((today - last_pub_date).days / 365.25, 1)
        else:
            last_pub_date = None
            years_since = None

        # Expected republication: based on the MOST RELEVANT tender
        expected_repub = best_tender.get("expected_republication") if "expected_republication" in group.columns else None
        if pd.notna(expected_repub):
            expected_repub_quarter = get_quarter_label(expected_repub)
        else:
            expected_repub = None
            expected_repub_quarter = ""

        # Contact date (based on most relevant tender's republication)
        if expected_repub:
            contact_date = expected_repub - relativedelta(months=lead_months)
            contact_quarter = get_quarter_label(contact_date)
            days_until = (contact_date - today).days
        else:
            contact_quarter = ""
            days_until = None

        # Best priority from group
        priority_order = {"OVERDUE": 0, "URGENT": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4, "UNKNOWN": 5}
        best_priority = "UNKNOWN"
        if "priority" in group.columns:
            for _, row in group.iterrows():
                row_priority = row.get("priority", "UNKNOWN")
                if priority_order.get(row_priority, 5) < priority_order.get(best_priority, 5):
                    best_priority = row_priority

        # Competitors
        competitors = set()
        if "competitor_win" in group.columns:
            for comp in group["competitor_win"].dropna():
                if comp:
                    competitors.add(comp)
        competitors_str = ", ".join(sorted(competitors)) if competitors else ""

        # Contract value
        total_value = 0
        if "contract_value" in group.columns:
            values = pd.to_numeric(group["contract_value"], errors="coerce")
            total_value = values.sum()

        # Tender info
        tender_count = len(group)
        tender_titles = group["title"].dropna().tolist()[:3]
        titles_str = " | ".join([t[:50] for t in tender_titles])

        # Seasonal pattern
        publication_pattern = get_seasonal_pattern(pub_dates.tolist()) if len(pub_dates) > 1 else None

        # Relevance score (0-100)
        score = 0
        score_parts = []

        # 1. Core competitor als winnaar → maximale score (override)
        has_core_competitor = False
        if "is_core_competitor_win" in group.columns:
            has_core_competitor = group["is_core_competitor_win"].any()
        elif "match_type" in group.columns:
            has_core_competitor = group["match_type"].str.lower().str.contains("kernconcurrent", na=False).any()

        if has_core_competitor:
            score = 100
            core_names = []
            if "competitor_win" in group.columns:
                core_names = list(group[
                    group.get("is_core_competitor_win", pd.Series([False]*len(group), index=group.index))
                ]["competitor_win"].dropna().unique())
            score_parts.append(f"Kernconcurrent als winnaar: {', '.join(core_names) if core_names else competitors_str}")
        else:
            # 2. Gebruik de hoogste keyword_score uit de groep als basis
            if "keyword_score" in group.columns:
                max_kw_score = pd.to_numeric(group["keyword_score"], errors="coerce").max()
                if pd.notna(max_kw_score) and max_kw_score > 0:
                    score = int(max_kw_score)
                    score_parts.append(f"Gewogen keyword score: {score}")
            else:
                # Fallback: oude logica als keyword_score niet beschikbaar
                if "match_type" in group.columns:
                    match_types = group["match_type"].dropna().tolist()
                    has_both = any("keyword+cpv" in str(m).lower() for m in match_types)
                    has_keyword = any("keyword" in str(m).lower() for m in match_types)
                    has_cpv = any("cpv" in str(m).lower() for m in match_types)
                    if has_both:
                        score += 50
                    elif has_keyword and has_cpv:
                        score += 40
                    elif has_keyword:
                        score += 25
                    elif has_cpv:
                        score += 20

            # 3. Bonus: herhaalde aanbesteder
            if tender_count >= 3:
                bonus = min(15, score // 5)  # proportioneel, geen overkill
                score = min(100, score + bonus)
                score_parts.append(f"+{bonus} herhaalde aanbesteder ({tender_count} tenders)")
            elif tender_count >= 2:
                bonus = min(8, score // 8)
                score = min(100, score + bonus)
                score_parts.append(f"+{bonus} meerdere tenders ({tender_count})")

            # 4. Bonus: hoge contractwaarde
            if total_value > 100000:
                score = min(100, score + 10)
                score_parts.append(f"+10 hoge contractwaarde (EUR {total_value:,.0f})")
            elif total_value > 25000:
                score = min(100, score + 5)
                score_parts.append(f"+5 contractwaarde (EUR {total_value:,.0f})")

            # 5. Bonus: secundaire concurrent info
            if competitors_str:
                score = min(100, score + 3)
                score_parts.append(f"+3 concurrent-info ({competitors_str})")

        score = min(score, 100)
        score_explanation = "; ".join(score_parts)

        # Republication basis explanation (from most relevant tender)
        repub_basis = ""
        if "republication_basis" in group.columns:
            basis = best_tender.get("republication_basis")
            if pd.notna(basis):
                repub_basis = basis

        org_data.append({
            "organization": org_name,
            "city": city,
            "last_publication_date": last_pub_date,
            "publication_pattern": publication_pattern if publication_pattern else "",
            "years_since_publication": years_since,
            "expected_republication": expected_repub,
            "expected_republication_quarter": expected_repub_quarter,
            "republication_basis": repub_basis,
            "contact_quarter": contact_quarter,
            "days_until_contact": days_until,
            "priority": best_priority,
            "relevance_score": score,
            "relevance_explanation": score_explanation,
            "warmth_score": round(score),  # keep for backward compat
            "competitors_won": competitors_str,
            "total_contract_value": total_value,
            "tender_count": tender_count,
            "tender_titles": titles_str,
        })

    result_df = pd.DataFrame(org_data)

    # Sort by relevance score (highest first)
    if not result_df.empty:
        result_df = result_df.sort_values(
            ["relevance_score", "years_since_publication"],
            ascending=[False, False],
            na_position="last"
        )

    return result_df


def get_organizations_to_contact(
    org_df: pd.DataFrame,
    max_days: int = 180,
    priorities: list = None,
) -> pd.DataFrame:
    """Filter organizations by priority and timeframe."""
    if org_df.empty:
        return org_df

    if priorities is None:
        priorities = ["OVERDUE", "URGENT", "HIGH"]

    result = org_df.copy()
    result = result[result["priority"].isin(priorities)]
    result = result[
        (result["days_until_contact"].isna()) |
        (result["days_until_contact"] <= max_days)
    ]

    return result


def get_organization_summary(org_df: pd.DataFrame) -> dict:
    """Get summary statistics for organization analysis."""
    if org_df.empty:
        return {
            "total_organizations": 0,
            "urgent_organizations": 0,
            "with_competitor_intel": 0,
            "total_contract_value": 0,
            "avg_warmth_score": 0,
        }

    priority_counts = org_df["priority"].value_counts().to_dict()

    return {
        "total_organizations": len(org_df),
        "urgent_organizations": priority_counts.get("OVERDUE", 0) + priority_counts.get("URGENT", 0),
        "with_competitor_intel": len(org_df[org_df["competitors_won"] != ""]),
        "total_contract_value": org_df["total_contract_value"].sum(),
        "avg_warmth_score": round(org_df["warmth_score"].mean(), 1),
        "priority_breakdown": priority_counts,
    }


def export_call_list(org_df: pd.DataFrame) -> pd.DataFrame:
    """Create a clean export for analysis results."""
    if org_df.empty:
        return pd.DataFrame()

    cols = {
        "Organisatie": org_df["organization"],
        "Plaats": org_df["city"],
        "Relevantie": org_df["relevance_score"],
        "Laatste publicatie": org_df["last_publication_date"],
        "Jaren geleden": org_df["years_since_publication"],
        "Verwachte herpublicatie": org_df["expected_republication_quarter"],
        "Basis schatting": org_df["republication_basis"] if "republication_basis" in org_df.columns else "",
        "Concurrenten": org_df["competitors_won"],
        "Contract waarde": org_df["total_contract_value"].apply(
            lambda x: f"EUR {x:,.0f}" if x > 0 else ""
        ),
        "Seizoenspatroon": org_df["publication_pattern"] if "publication_pattern" in org_df.columns else "",
        "Aantal tenders": org_df["tender_count"],
        "Tenders": org_df["tender_titles"],
        "Score uitleg": org_df["relevance_explanation"],
    }
    export_df = pd.DataFrame(cols)

    return export_df
