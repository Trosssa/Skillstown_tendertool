"""
Relevance filtering for TenderNed tenders.
Filters based on search terms and CPV codes.

Fase 6 wijzigingen (2026-02-23):
- Gewogen keyword-scoring: frequentie × gewicht per term
- Core-concurrent als winnaar → keyword_score override naar 100
- calculate_keyword_score() toegevoegd
"""

import pandas as pd
import re
from typing import Optional

from .config import (
    SEARCH_TERMS, SECTOR_TERMS, ALL_CPV_CODES, NEGATIVE_KEYWORDS,
    COMPETITORS, CORE_COMPETITORS, ALL_CORE_COMPETITOR_TERMS, TERM_WEIGHTS,
)

# Gecombineerde zoektermen: basis + sector-specifiek
ALL_SEARCH_TERMS = SEARCH_TERMS + [t for t in SECTOR_TERMS if t not in SEARCH_TERMS]


def create_search_pattern(terms: list[str]) -> str:
    """
    Create a regex pattern for searching multiple terms.
    Handles word boundaries and special characters.
    """
    escaped_terms = [re.escape(term) for term in terms]
    patterns = []
    for term in escaped_terms:
        if len(term) <= 4:
            patterns.append(rf"\b{term}\b")
        else:
            patterns.append(term)
    return "|".join(patterns)


def is_core_competitor_win(winning_company: str) -> tuple[bool, str]:
    """
    Check if a tender was won by one of the 7 core competitors.

    Returns:
        (is_core_win: bool, competitor_name: str)
    """
    if not winning_company or pd.isna(winning_company):
        return False, ""

    company_lower = str(winning_company).lower().strip()

    for display_name, variants in CORE_COMPETITORS.items():
        for variant in variants:
            if variant.lower() in company_lower:
                return True, display_name

    return False, ""


def calculate_keyword_score(
    title: str,
    description: str,
    winning_company: str = "",
    term_weights: Optional[dict] = None,
) -> tuple[int, list[str]]:
    """
    Calculate a weighted keyword score for a tender.

    Scoring:
    - Core competitor as winner → score 100 (maximum, override)
    - Otherwise: sum of (term_weight × occurrence_count) per matched term
    - Score is normalized to 0-100

    Returns:
        (score: int 0-100, matched_terms: list of matched term names)
    """
    if term_weights is None:
        term_weights = TERM_WEIGHTS

    # Core competitor override — strongest signal
    if winning_company:
        is_core, competitor_name = is_core_competitor_win(winning_company)
        if is_core:
            return 100, [f"KERNCONCURRENT: {competitor_name}"]

    # Combine text to search
    combined_text = " ".join([
        str(title) if pd.notna(title) else "",
        str(description) if pd.notna(description) else "",
    ]).lower()

    if not combined_text.strip():
        return 0, []

    raw_score = 0
    matched_terms = []

    for term, weight in term_weights.items():
        # Count occurrences (case-insensitive)
        term_lower = term.lower()
        count = combined_text.count(term_lower)
        if count > 0:
            raw_score += weight * count
            matched_terms.append(term)

    if not matched_terms:
        return 0, []

    # Normalize: raw score → 0-100
    # Max theoretical score: a tender mentioning every weight-5 term 3x each
    # Practical cap: normalize against a "perfect tender" score of ~60 raw points
    NORMALIZATION_CAP = 60
    normalized = min(100, int((raw_score / NORMALIZATION_CAP) * 100))

    return normalized, matched_terms


def filter_by_keywords(
    df: pd.DataFrame,
    search_terms: Optional[list[str]] = None,
    search_columns: Optional[list[str]] = None,
    include_sector_terms: bool = True,
) -> pd.DataFrame:
    """
    Filter tenders by keyword search in title and description.
    """
    if search_terms is None:
        search_terms = ALL_SEARCH_TERMS if include_sector_terms else SEARCH_TERMS

    if search_columns is None:
        search_columns = ["title", "description"]

    pattern = create_search_pattern(search_terms)
    mask = pd.Series([False] * len(df), index=df.index)

    for col in search_columns:
        if col in df.columns:
            col_match = df[col].str.contains(pattern, case=False, na=False, regex=True)
            mask = mask | col_match

    return df[mask].copy()


def filter_by_cpv_codes(
    df: pd.DataFrame,
    cpv_codes: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    Filter tenders by CPV codes.
    """
    if cpv_codes is None:
        cpv_codes = ALL_CPV_CODES

    if "cpv_codes" not in df.columns:
        return df.iloc[0:0].copy()

    cpv_pattern = "|".join([code.split("-")[0] for code in cpv_codes])
    mask = df["cpv_codes"].str.contains(cpv_pattern, case=False, na=False, regex=True)

    return df[mask].copy()


def filter_relevant_tenders(
    df: pd.DataFrame,
    search_terms: Optional[list[str]] = None,
    cpv_codes: Optional[list[str]] = None,
    use_keywords: bool = True,
    use_cpv: bool = True,
    include_sector_terms: bool = True,
) -> pd.DataFrame:
    """
    Filter tenders using keyword search and/or CPV codes.
    Also catches tenders won by core competitors, even without keyword match.

    Returns tenders with added 'match_type' and 'keyword_score' columns.
    """
    if search_terms is None:
        search_terms = ALL_SEARCH_TERMS if include_sector_terms else SEARCH_TERMS
    if cpv_codes is None:
        cpv_codes = ALL_CPV_CODES

    keyword_mask = pd.Series([False] * len(df), index=df.index)
    cpv_mask = pd.Series([False] * len(df), index=df.index)
    core_competitor_mask = pd.Series([False] * len(df), index=df.index)

    # Keyword filter
    if use_keywords:
        pattern = create_search_pattern(search_terms)
        for col in ["title", "description"]:
            if col in df.columns:
                col_match = df[col].str.contains(pattern, case=False, na=False, regex=True)
                keyword_mask = keyword_mask | col_match

    # CPV filter
    if use_cpv and "cpv_codes" in df.columns:
        cpv_pattern = "|".join([code.split("-")[0] for code in cpv_codes])
        cpv_mask = df["cpv_codes"].str.contains(cpv_pattern, case=False, na=False, regex=True)

    # Core competitor filter — include these regardless of keyword/CPV match
    if "winning_company" in df.columns:
        core_competitor_mask = df["winning_company"].apply(
            lambda x: is_core_competitor_win(x)[0]
        )

    combined_mask = keyword_mask | cpv_mask | core_competitor_mask

    result = df[combined_mask].copy()

    # Add match type
    result["match_type"] = "Geen"
    kw = keyword_mask[combined_mask]
    cpv = cpv_mask[combined_mask]
    cc = core_competitor_mask[combined_mask]

    result.loc[cc, "match_type"] = "Kernconcurrent"
    result.loc[kw & cpv & ~cc, "match_type"] = "Zoekterm + CPV"
    result.loc[kw & ~cpv & ~cc, "match_type"] = "Zoekterm"
    result.loc[~kw & cpv & ~cc, "match_type"] = "CPV-code"

    return result


def get_matched_terms(text: str, search_terms: Optional[list[str]] = None) -> list[str]:
    """Get list of search terms that match in a given text."""
    if search_terms is None:
        search_terms = ALL_SEARCH_TERMS

    if not text or pd.isna(text):
        return []

    text_lower = text.lower()
    return [term for term in search_terms if term.lower() in text_lower]


def get_matched_cpv_codes(cpv_string: str, cpv_codes: Optional[list[str]] = None) -> list[str]:
    """Get list of relevant CPV codes found in a CPV code string."""
    if cpv_codes is None:
        cpv_codes = ALL_CPV_CODES

    if not cpv_string or pd.isna(cpv_string):
        return []

    matched = []
    for code in cpv_codes:
        code_prefix = code.split("-")[0]
        if code_prefix in str(cpv_string):
            matched.append(code)

    return matched


def add_match_details(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add columns with details about why each tender was matched.
    Includes weighted keyword_score per tender.
    """
    result = df.copy()

    result["matched_terms"] = ""
    result["matched_cpv"] = ""
    result["keyword_score"] = 0

    for idx, row in result.iterrows():
        title = row.get("title", "")
        description = row.get("description", "")
        winning_company = row.get("winning_company", "")

        # Matched terms (for display)
        terms = set()
        terms.update(get_matched_terms(str(title) if pd.notna(title) else ""))
        terms.update(get_matched_terms(str(description) if pd.notna(description) else ""))
        result.at[idx, "matched_terms"] = ", ".join(terms)

        # Matched CPV codes
        if "cpv_codes" in result.columns:
            result.at[idx, "matched_cpv"] = ", ".join(
                get_matched_cpv_codes(row.get("cpv_codes", ""))
            )

        # Weighted keyword score
        score, _ = calculate_keyword_score(title, description, winning_company)
        result.at[idx, "keyword_score"] = score

    return result


def contains_negative_keywords(text: str, negative_terms: Optional[list[str]] = None) -> bool:
    """Check if text contains negative keywords (indicating irrelevant tender)."""
    if negative_terms is None:
        negative_terms = NEGATIVE_KEYWORDS

    if not text or pd.isna(text):
        return False

    text_lower = text.lower()
    return any(term.lower() in text_lower for term in negative_terms)


def filter_out_negative_keywords(
    df: pd.DataFrame,
    negative_terms: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Remove tenders that contain negative keywords (e.g., job postings)."""
    if negative_terms is None:
        negative_terms = NEGATIVE_KEYWORDS

    result = df.copy()
    negative_mask = pd.Series([False] * len(result), index=result.index)

    for col in ["title", "description", "lot_title", "lot_description"]:
        if col in result.columns:
            col_negative = result[col].apply(
                lambda x: contains_negative_keywords(x, negative_terms)
            )
            negative_mask = negative_mask | col_negative

    return result[~negative_mask].copy()


def detect_competitor_wins(
    df: pd.DataFrame,
    competitors: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    Add columns indicating if tender was won by a known competitor.
    Distinguishes between core competitors (max score) and secondary competitors.
    """
    if competitors is None:
        competitors = COMPETITORS

    result = df.copy()
    result["competitor_win"] = ""
    result["is_competitor_win"] = False
    result["is_core_competitor_win"] = False

    if "winning_company" not in result.columns:
        return result

    for idx, row in result.iterrows():
        company = str(row.get("winning_company", "")).lower()
        if not company or company == "nan":
            continue

        # Check core competitors first
        is_core, core_name = is_core_competitor_win(row.get("winning_company", ""))
        if is_core:
            result.at[idx, "competitor_win"] = core_name
            result.at[idx, "is_competitor_win"] = True
            result.at[idx, "is_core_competitor_win"] = True
            continue

        # Check secondary competitors
        matched = [c for c in competitors if c.lower() in company]
        if matched:
            result.at[idx, "competitor_win"] = ", ".join(matched)
            result.at[idx, "is_competitor_win"] = True

    return result


def get_competitor_summary(df: pd.DataFrame) -> dict:
    """Get summary of wins by competitor."""
    if "competitor_win" not in df.columns:
        return {}

    competitor_df = df[df["is_competitor_win"] == True]
    if len(competitor_df) == 0:
        return {}

    wins = {}
    for _, row in competitor_df.iterrows():
        for comp in row["competitor_win"].split(", "):
            if comp:
                wins[comp] = wins.get(comp, 0) + 1

    return dict(sorted(wins.items(), key=lambda x: x[1], reverse=True))
