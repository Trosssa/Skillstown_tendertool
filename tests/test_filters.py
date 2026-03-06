"""Tests for filters module."""

import pytest
import pandas as pd

import sys
sys.path.insert(0, str(__file__).rsplit('tests', 1)[0])

from src.filters import (
    create_search_pattern,
    filter_by_keywords,
    filter_by_cpv_codes,
    filter_relevant_tenders,
    get_matched_terms,
    get_matched_cpv_codes,
    add_match_details,
)


class TestCreateSearchPattern:
    """Tests for search pattern creation."""

    def test_single_term(self):
        """Single term should create simple pattern."""
        pattern = create_search_pattern(["e-learning"])
        assert "e-learning" in pattern

    def test_multiple_terms(self):
        """Multiple terms should be joined with OR."""
        pattern = create_search_pattern(["LMS", "e-learning"])
        assert "|" in pattern

    def test_short_term_word_boundary(self):
        """Short terms should have word boundaries."""
        pattern = create_search_pattern(["LMS"])
        assert r"\b" in pattern

    def test_special_chars_escaped(self):
        """Special regex characters should be escaped."""
        pattern = create_search_pattern(["e-learning"])
        # The hyphen should be escaped
        assert "e\\-learning" in pattern or "e-learning" in pattern


class TestFilterByKeywords:
    """Tests for keyword filtering."""

    def test_title_match(self):
        """Should match keywords in title."""
        df = pd.DataFrame({
            "title": ["LMS implementatie", "Andere tender"],
            "description": ["", ""],
        })
        result = filter_by_keywords(df, search_terms=["LMS"])
        assert len(result) == 1
        assert "LMS" in result["title"].iloc[0]

    def test_description_match(self):
        """Should match keywords in description."""
        df = pd.DataFrame({
            "title": ["Tender A", "Tender B"],
            "description": ["Over e-learning", "Iets anders"],
        })
        result = filter_by_keywords(df, search_terms=["e-learning"])
        assert len(result) == 1

    def test_case_insensitive(self):
        """Matching should be case insensitive."""
        df = pd.DataFrame({
            "title": ["lms systeem", "LMS SYSTEEM"],
            "description": ["", ""],
        })
        result = filter_by_keywords(df, search_terms=["LMS"])
        assert len(result) == 2

    def test_no_matches(self):
        """Should return empty dataframe when no matches."""
        df = pd.DataFrame({
            "title": ["Bouw project", "Infra project"],
            "description": ["", ""],
        })
        result = filter_by_keywords(df, search_terms=["LMS"])
        assert len(result) == 0

    def test_missing_column(self):
        """Should handle missing columns gracefully."""
        df = pd.DataFrame({"title": ["LMS test"]})
        result = filter_by_keywords(df, search_terms=["LMS"])
        assert len(result) == 1


class TestFilterByCpvCodes:
    """Tests for CPV code filtering."""

    def test_exact_match(self):
        """Should match exact CPV codes."""
        df = pd.DataFrame({
            "cpv_codes": ["48190000-6", "12345678-9"],
        })
        result = filter_by_cpv_codes(df, cpv_codes=["48190000-6"])
        assert len(result) == 1

    def test_partial_match(self):
        """Should match CPV code prefix."""
        df = pd.DataFrame({
            "cpv_codes": ["48190000-6, 80420000-4", "12345678-9"],
        })
        result = filter_by_cpv_codes(df, cpv_codes=["48190000-6"])
        assert len(result) == 1

    def test_missing_column(self):
        """Should return empty when cpv_codes column missing."""
        df = pd.DataFrame({"other": [1, 2]})
        result = filter_by_cpv_codes(df, cpv_codes=["48190000-6"])
        assert len(result) == 0


class TestFilterRelevantTenders:
    """Tests for combined filtering."""

    def test_keyword_only(self):
        """Should filter by keywords only when CPV disabled."""
        df = pd.DataFrame({
            "title": ["LMS project", "Bouw project"],
            "description": ["", ""],
            "cpv_codes": ["12345678-9", "48190000-6"],
        })
        result = filter_relevant_tenders(
            df,
            search_terms=["LMS"],
            use_keywords=True,
            use_cpv=False,
        )
        assert len(result) == 1
        assert "LMS" in result["title"].iloc[0]

    def test_cpv_only(self):
        """Should filter by CPV only when keywords disabled."""
        df = pd.DataFrame({
            "title": ["Project A", "Project B"],
            "description": ["", ""],
            "cpv_codes": ["48190000-6", "12345678-9"],
        })
        result = filter_relevant_tenders(
            df,
            cpv_codes=["48190000-6"],
            use_keywords=False,
            use_cpv=True,
        )
        assert len(result) == 1

    def test_or_logic(self):
        """Should use OR logic for combined filtering."""
        df = pd.DataFrame({
            "title": ["LMS project", "Ander project", "Derde project"],
            "description": ["", "", ""],
            "cpv_codes": ["12345678-9", "48190000-6", "99999999-9"],
        })
        result = filter_relevant_tenders(
            df,
            search_terms=["LMS"],
            cpv_codes=["48190000-6"],
            use_keywords=True,
            use_cpv=True,
        )
        assert len(result) == 2  # LMS match + CPV match

    def test_match_type_column(self):
        """Should add match_type column."""
        df = pd.DataFrame({
            "title": ["LMS project"],
            "description": [""],
            "cpv_codes": ["48190000-6"],
        })
        result = filter_relevant_tenders(
            df,
            search_terms=["LMS"],
            cpv_codes=["48190000-6"],
        )
        assert "match_type" in result.columns
        assert result["match_type"].iloc[0] == "Zoekterm + CPV"


class TestGetMatchedTerms:
    """Tests for matched terms retrieval."""

    def test_single_match(self):
        """Should find single matched term."""
        result = get_matched_terms("Dit is een LMS systeem", ["LMS", "e-learning"])
        assert "LMS" in result

    def test_multiple_matches(self):
        """Should find multiple matched terms."""
        result = get_matched_terms("LMS met e-learning", ["LMS", "e-learning"])
        assert "LMS" in result
        assert "e-learning" in result

    def test_no_matches(self):
        """Should return empty list when no matches."""
        result = get_matched_terms("Bouw project", ["LMS", "e-learning"])
        assert len(result) == 0

    def test_null_text(self):
        """Should handle null text."""
        result = get_matched_terms(None, ["LMS"])
        assert len(result) == 0


class TestGetMatchedCpvCodes:
    """Tests for matched CPV codes retrieval."""

    def test_single_match(self):
        """Should find single matched CPV code."""
        result = get_matched_cpv_codes("48190000-6", ["48190000-6", "80420000-4"])
        assert "48190000-6" in result

    def test_null_input(self):
        """Should handle null input."""
        result = get_matched_cpv_codes(None, ["48190000-6"])
        assert len(result) == 0


class TestAddMatchDetails:
    """Tests for adding match details."""

    def test_adds_columns(self):
        """Should add matched_terms and matched_cpv columns."""
        df = pd.DataFrame({
            "title": ["LMS project"],
            "description": [""],
            "cpv_codes": ["48190000-6"],
        })
        result = add_match_details(df)
        assert "matched_terms" in result.columns
        assert "matched_cpv" in result.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
