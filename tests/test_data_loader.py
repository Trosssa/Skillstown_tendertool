"""Tests for data_loader module."""

import pytest
import pandas as pd
from io import BytesIO

import sys
sys.path.insert(0, str(__file__).rsplit('tests', 1)[0])

from src.data_loader import (
    normalize_column_names,
    parse_dates,
    clean_text_columns,
    validate_data,
    get_column_info,
)


class TestNormalizeColumnNames:
    """Tests for column name normalization."""

    def test_lowercase_conversion(self):
        """Column names should be converted to lowercase."""
        df = pd.DataFrame({"Title": [1], "DESCRIPTION": [2]})
        result = normalize_column_names(df)
        assert "title" in result.columns
        assert "description" in result.columns

    def test_space_to_underscore(self):
        """Spaces should be replaced with underscores."""
        df = pd.DataFrame({"tender title": [1]})
        result = normalize_column_names(df)
        assert "title" in result.columns

    def test_dutch_column_mapping(self):
        """Dutch column names should be mapped correctly."""
        df = pd.DataFrame({
            "titel": ["Test"],
            "omschrijving": ["Desc"],
            "publicatiedatum": ["2024-01-01"],
            "aanbestedende_dienst": ["Org"],
        })
        result = normalize_column_names(df)
        assert "title" in result.columns
        assert "description" in result.columns
        assert "publication_date" in result.columns
        assert "organization" in result.columns

    def test_english_column_mapping(self):
        """English column names should be mapped correctly."""
        df = pd.DataFrame({
            "title": ["Test"],
            "description": ["Desc"],
            "publisheddate": ["2024-01-01"],
        })
        result = normalize_column_names(df)
        assert "title" in result.columns
        assert "description" in result.columns
        assert "publication_date" in result.columns


class TestParseDates:
    """Tests for date parsing."""

    def test_iso_date_format(self):
        """ISO format dates should be parsed."""
        df = pd.DataFrame({"publication_date": ["2024-01-15"]})
        result = parse_dates(df)
        assert pd.notna(result["publication_date"].iloc[0])

    def test_european_date_format(self):
        """European format dates (DD-MM-YYYY) should be parsed."""
        df = pd.DataFrame({"publication_date": ["15-01-2024"]})
        result = parse_dates(df)
        assert pd.notna(result["publication_date"].iloc[0])

    def test_invalid_date_handling(self):
        """Invalid dates should become NaT."""
        df = pd.DataFrame({"publication_date": ["not a date"]})
        result = parse_dates(df)
        assert pd.isna(result["publication_date"].iloc[0])

    def test_missing_column_handling(self):
        """Missing date columns should not cause errors."""
        df = pd.DataFrame({"other_column": [1]})
        result = parse_dates(df)
        assert "other_column" in result.columns


class TestCleanTextColumns:
    """Tests for text column cleaning."""

    def test_whitespace_stripping(self):
        """Whitespace should be stripped from text."""
        df = pd.DataFrame({"title": ["  Test Title  "]})
        result = clean_text_columns(df)
        assert result["title"].iloc[0] == "Test Title"

    def test_null_handling(self):
        """Null values should become empty strings."""
        df = pd.DataFrame({"title": [None]})
        result = clean_text_columns(df)
        assert result["title"].iloc[0] == ""

    def test_missing_column_handling(self):
        """Missing columns should not cause errors."""
        df = pd.DataFrame({"other": ["test"]})
        result = clean_text_columns(df)
        assert "other" in result.columns


class TestValidateData:
    """Tests for data validation."""

    def test_valid_data(self):
        """Valid data should pass validation."""
        df = pd.DataFrame({
            "title": ["Test"],
            "publication_date": [pd.Timestamp("2024-01-01")],
            "organization": ["Org"],
        })
        is_valid, issues = validate_data(df)
        assert is_valid
        assert len([i for i in issues if not i.startswith("Waarschuwing")]) == 0

    def test_missing_required_columns(self):
        """Missing required columns should be reported."""
        df = pd.DataFrame({"other": [1]})
        is_valid, issues = validate_data(df)
        assert not is_valid
        assert any("Ontbrekende kolommen" in i for i in issues)

    def test_empty_dataframe(self):
        """Empty dataframe should be reported."""
        df = pd.DataFrame({
            "title": [],
            "publication_date": [],
            "organization": [],
        })
        is_valid, issues = validate_data(df)
        assert not is_valid
        assert any("Geen data" in i for i in issues)

    def test_invalid_dates_warning(self):
        """Low valid date ratio should generate warning."""
        df = pd.DataFrame({
            "title": ["A", "B", "C", "D"],
            "publication_date": [pd.NaT, pd.NaT, pd.NaT, pd.Timestamp("2024-01-01")],
            "organization": ["O1", "O2", "O3", "O4"],
        })
        is_valid, issues = validate_data(df)
        assert any("Waarschuwing" in i for i in issues)


class TestGetColumnInfo:
    """Tests for column info retrieval."""

    def test_column_count(self):
        """Should return correct column count."""
        df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
        info = get_column_info(df)
        assert info["total_columns"] == 3

    def test_row_count(self):
        """Should return correct row count."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        info = get_column_info(df)
        assert info["total_rows"] == 3

    def test_date_columns_detection(self):
        """Should detect date columns."""
        df = pd.DataFrame({
            "publication_date": [1],
            "award_date": [2],
            "other": [3],
        })
        info = get_column_info(df)
        assert "publication_date" in info["date_columns_found"]
        assert "award_date" in info["date_columns_found"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
