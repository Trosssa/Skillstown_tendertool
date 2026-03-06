"""
Automated tests for SkillsTown TenderNed Analyzer.
Run with: python -m pytest tests/ -v
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO

# Import modules to test
import sys
sys.path.insert(0, '..')

from src.config import (
    SEARCH_TERMS, ALL_CPV_CODES, CPV_DESCRIPTIONS,
    CORE_COMPETITORS, ALL_CORE_COMPETITOR_TERMS, TERM_WEIGHTS,
)
from src.data_loader import normalize_column_names, parse_dates, clean_text_columns, validate_data
from src.filters import (
    create_search_pattern,
    filter_by_keywords,
    filter_by_cpv_codes,
    filter_relevant_tenders,
    get_matched_terms,
    get_matched_cpv_codes,
    is_core_competitor_win,
    calculate_keyword_score,
)
from src.predictor import (
    get_reference_date,
    calculate_expected_republication,
    calculate_contact_date,
    assign_priority,
    calculate_confidence_score,
    predict_republication_dates,
    get_priority_summary,
    get_seasonal_pattern,
)
from src.ai_scorer import (
    is_anthropic_available,
    should_analyze_with_ai,
    create_tender_hash,
    parse_ai_response,
    get_skillstown_context,
    create_scoring_prompt,
    get_ai_summary,
)
from src.org_analyzer import (
    get_quarter_label,
    get_quarter_sort_key,
    aggregate_organizations,
    get_organizations_to_contact,
    get_organization_summary,
    export_call_list,
)


class TestConfig:
    """Test configuration module."""

    def test_search_terms_not_empty(self):
        assert len(SEARCH_TERMS) > 0

    def test_cpv_codes_not_empty(self):
        assert len(ALL_CPV_CODES) > 0

    def test_cpv_descriptions_match_codes(self):
        for code in ALL_CPV_CODES:
            assert code in CPV_DESCRIPTIONS, f"Missing description for CPV code {code}"

    def test_core_competitors_has_seven(self):
        """Exact 7 kernconcurrenten verwacht (opgegeven door sales)."""
        assert len(CORE_COMPETITORS) == 7

    def test_core_competitors_expected_names(self):
        expected = {"Plusport", "GoodHabitz", "New Heroes", "StudyTube",
                    "Courseware", "Online Academie", "Uplearning"}
        assert set(CORE_COMPETITORS.keys()) == expected

    def test_core_competitors_all_have_variants(self):
        """Elke concurrent heeft minstens 2 variaties (inclusief basisnaam)."""
        for name, variants in CORE_COMPETITORS.items():
            assert len(variants) >= 2, f"{name} heeft te weinig variaties"

    def test_all_core_competitor_terms_not_empty(self):
        assert len(ALL_CORE_COMPETITOR_TERMS) > 7  # meer dan 7 want variaties

    def test_term_weights_all_positive(self):
        for term, weight in TERM_WEIGHTS.items():
            assert weight > 0, f"Gewicht voor '{term}' moet positief zijn"

    def test_term_weights_lms_highest(self):
        """LMS moet het hoogste gewicht hebben (kern product)."""
        assert TERM_WEIGHTS["LMS"] == max(TERM_WEIGHTS.values())

    def test_search_terms_match_term_weights_keys(self):
        """SEARCH_TERMS moet gelijk zijn aan de keys van TERM_WEIGHTS."""
        assert set(SEARCH_TERMS) == set(TERM_WEIGHTS.keys())


class TestDataLoader:
    """Test data loading functions."""

    def test_normalize_column_names_english(self):
        df = pd.DataFrame({
            "Title": ["Test"],
            "Description": ["Desc"],
            "PublishedDate": ["2024-01-01"],
        })
        result = normalize_column_names(df)
        assert "title" in result.columns
        assert "description" in result.columns
        assert "publication_date" in result.columns

    def test_normalize_column_names_dutch(self):
        df = pd.DataFrame({
            "Titel": ["Test"],
            "Omschrijving": ["Desc"],
            "Publicatiedatum": ["2024-01-01"],
            "Aanbestedende_dienst": ["Org"],
        })
        result = normalize_column_names(df)
        assert "title" in result.columns
        assert "description" in result.columns
        assert "publication_date" in result.columns
        assert "organization" in result.columns

    def test_parse_dates_valid(self):
        df = pd.DataFrame({
            "publication_date": ["2024-01-15", "15-01-2024", "2024/01/15"],
        })
        result = parse_dates(df)
        assert pd.api.types.is_datetime64_any_dtype(result["publication_date"])

    def test_parse_dates_invalid(self):
        df = pd.DataFrame({
            "publication_date": ["invalid", "not a date", ""],
        })
        result = parse_dates(df)
        assert result["publication_date"].isna().all()

    def test_clean_text_columns(self):
        df = pd.DataFrame({
            "title": ["  Test Title  ", None, "Normal"],
            "description": ["Desc", "  Spaced  ", None],
        })
        result = clean_text_columns(df)
        assert result["title"].iloc[0] == "Test Title"
        assert result["title"].iloc[1] == ""
        assert result["description"].iloc[1] == "Spaced"

    def test_validate_data_valid(self):
        df = pd.DataFrame({
            "title": ["Test"],
            "publication_date": [datetime.now()],
            "organization": ["Org"],
        })
        is_valid, issues = validate_data(df)
        assert is_valid
        assert len([i for i in issues if not i.startswith("Waarschuwing")]) == 0

    def test_validate_data_missing_columns(self):
        df = pd.DataFrame({
            "title": ["Test"],
        })
        is_valid, issues = validate_data(df)
        assert not is_valid
        assert any("Ontbrekende kolommen" in i for i in issues)

    def test_validate_data_empty(self):
        df = pd.DataFrame(columns=["title", "publication_date", "organization"])
        is_valid, issues = validate_data(df)
        assert not is_valid
        assert any("Geen data" in i for i in issues)


class TestFilters:
    """Test filtering functions."""

    def test_create_search_pattern(self):
        pattern = create_search_pattern(["LMS", "e-learning"])
        assert "LMS" in pattern
        # e-learning is escaped as e\-learning in regex
        assert "e" in pattern and "learning" in pattern

    def test_filter_by_keywords_match(self):
        df = pd.DataFrame({
            "title": ["LMS implementatie", "Andere tender", "E-learning platform"],
            "description": ["", "", ""],
        })
        result = filter_by_keywords(df)
        assert len(result) == 2
        assert "LMS" in result["title"].iloc[0]

    def test_filter_by_keywords_no_match(self):
        df = pd.DataFrame({
            "title": ["Wegenbouw project", "Catering diensten"],
            "description": ["Asfalt", "Eten"],
        })
        result = filter_by_keywords(df)
        assert len(result) == 0

    def test_filter_by_keywords_case_insensitive(self):
        df = pd.DataFrame({
            "title": ["lms systeem", "LMS SYSTEEM", "Lms Systeem"],
            "description": ["", "", ""],
        })
        result = filter_by_keywords(df, search_terms=["LMS"])
        assert len(result) == 3

    def test_filter_by_cpv_codes_match(self):
        df = pd.DataFrame({
            "cpv_codes": ["48190000-6", "12345678-9", "80420000-4"],
        })
        result = filter_by_cpv_codes(df)
        assert len(result) == 2

    def test_filter_by_cpv_codes_no_column(self):
        df = pd.DataFrame({
            "title": ["Test"],
        })
        result = filter_by_cpv_codes(df)
        assert len(result) == 0

    def test_get_matched_terms(self):
        text = "Dit is een LMS en e-learning platform"
        matches = get_matched_terms(text)
        assert "LMS" in matches
        assert "e-learning" in matches or "E-learning" in matches

    def test_get_matched_terms_empty(self):
        matches = get_matched_terms("")
        assert len(matches) == 0

    def test_get_matched_cpv_codes(self):
        cpv_string = "48190000-6, 80420000-4"
        matches = get_matched_cpv_codes(cpv_string)
        assert len(matches) >= 1

    # === Nieuwe tests Fase 6: core competitors en gewogen scoring ===

    def test_is_core_competitor_win_exact(self):
        """Exacte naam matcht als kernconcurrent."""
        is_core, name = is_core_competitor_win("GoodHabitz")
        assert is_core is True
        assert name == "GoodHabitz"

    def test_is_core_competitor_win_variant(self):
        """Variaties matchen ook."""
        is_core, name = is_core_competitor_win("Studytube B.V.")
        assert is_core is True
        assert name == "StudyTube"

    def test_is_core_competitor_win_case_insensitive(self):
        is_core, name = is_core_competitor_win("GOODHABITZ BV")
        assert is_core is True

    def test_is_core_competitor_win_no_match(self):
        """Onbekend bedrijf is geen kernconcurrent."""
        is_core, name = is_core_competitor_win("Rijkswaterstaat")
        assert is_core is False
        assert name == ""

    def test_is_core_competitor_win_empty(self):
        is_core, name = is_core_competitor_win("")
        assert is_core is False

    def test_calculate_keyword_score_core_competitor(self):
        """Core concurrent als winnaar geeft altijd score 100."""
        score, terms = calculate_keyword_score(
            title="Wegenbouw aanbesteding",
            description="Aanleg snelweg",
            winning_company="GoodHabitz",
        )
        assert score == 100
        assert any("KERNCONCURRENT" in t for t in terms)

    def test_calculate_keyword_score_high_weight_terms(self):
        """LMS (gewicht 5) scoort hoger dan 'webinar' (gewicht 2)."""
        score_lms, _ = calculate_keyword_score("LMS platform aanbesteding", "LMS implementatie voor de organisatie")
        score_webinar, _ = calculate_keyword_score("Webinar diensten", "Webinar platform voor medewerkers")
        assert score_lms > score_webinar

    def test_calculate_keyword_score_no_match(self):
        """Geen relevante termen geeft score 0."""
        score, terms = calculate_keyword_score("Wegenbouw project", "Aanleg snelweg A12")
        assert score == 0
        assert len(terms) == 0

    def test_calculate_keyword_score_multiple_occurrences(self):
        """Vaker voorkomen van een term geeft hogere score."""
        score_one, _ = calculate_keyword_score("LMS systeem", "Aanbesteding")
        score_three, _ = calculate_keyword_score("LMS platform LMS systeem", "LMS implementatie voor de gemeente")
        assert score_three > score_one

    def test_calculate_keyword_score_normalized_max_100(self):
        """Score nooit boven 100."""
        # Tender met heel veel LMS vermeldingen
        heavy_text = "LMS " * 50
        score, _ = calculate_keyword_score(heavy_text, heavy_text)
        assert score <= 100

    def test_filter_relevant_tenders_includes_core_competitor(self):
        """Tenders van kernconcurrenten komen door filter ook zonder keywords."""
        df = pd.DataFrame({
            "title": ["Wegenbouw project"],
            "description": ["Aanleg snelweg, geen e-learning"],
            "cpv_codes": ["45233120-6"],
            "winning_company": ["GoodHabitz"],
        })
        result = filter_relevant_tenders(df, use_keywords=True, use_cpv=True)
        assert len(result) == 1
        assert result.iloc[0]["match_type"] == "Kernconcurrent"

    def test_add_match_details_includes_keyword_score(self):
        """add_match_details voegt keyword_score kolom toe."""
        from src.filters import add_match_details
        df = pd.DataFrame({
            "title": ["LMS platform"],
            "description": ["E-learning oplossing voor de gemeente"],
            "winning_company": [""],
        })
        # Eerst filteren zodat match_type bestaat
        filtered = filter_relevant_tenders(df)
        result = add_match_details(filtered)
        assert "keyword_score" in result.columns
        assert result.iloc[0]["keyword_score"] > 0


class TestPredictor:
    """Test prediction functions."""

    def test_get_reference_date_contract_end(self):
        """Contract end date heeft hoogste prioriteit (exacte einddatum)."""
        row = pd.Series({
            "contract_end": datetime(2027, 1, 1),
            "publication_date": datetime(2023, 12, 1),
            "contract_start": datetime(2024, 2, 1),
        })
        ref_date, ref_type = get_reference_date(row)
        assert ref_date == datetime(2027, 1, 1)
        assert ref_type == "contract_end"

    def test_get_reference_date_publication(self):
        """Publication date is tweede prioriteit (budgetcyclus logica)."""
        row = pd.Series({
            "contract_end": None,
            "publication_date": datetime(2023, 12, 1),
            "contract_start": datetime(2024, 2, 1),
        })
        ref_date, ref_type = get_reference_date(row)
        assert ref_date == datetime(2023, 12, 1)
        assert ref_type == "publication_date"

    def test_get_reference_date_contract_start(self):
        """Contract start is fallback als geen andere datums beschikbaar."""
        row = pd.Series({
            "contract_end": None,
            "publication_date": None,
            "contract_start": datetime(2024, 2, 1),
        })
        ref_date, ref_type = get_reference_date(row)
        assert ref_date == datetime(2024, 2, 1)
        assert ref_type == "contract_start"

    def test_get_reference_date_none(self):
        """Geen datums beschikbaar geeft None terug."""
        row = pd.Series({
            "contract_end": None,
            "publication_date": None,
            "contract_start": None,
        })
        ref_date, ref_type = get_reference_date(row)
        assert ref_date is None
        assert ref_type == ""

    def test_calculate_expected_republication(self):
        ref_date = datetime(2024, 1, 1)
        result = calculate_expected_republication(ref_date, contract_years=3)
        assert result == datetime(2027, 1, 1)

    def test_calculate_contact_date(self):
        repub_date = datetime(2027, 1, 1)
        result = calculate_contact_date(repub_date, lead_months=4)
        assert result == datetime(2026, 9, 1)

    def test_assign_priority_urgent(self):
        assert assign_priority(15) == "URGENT"

    def test_assign_priority_high(self):
        assert assign_priority(60) == "HIGH"

    def test_assign_priority_medium(self):
        assert assign_priority(120) == "MEDIUM"

    def test_assign_priority_low(self):
        assert assign_priority(200) == "LOW"

    def test_assign_priority_overdue(self):
        assert assign_priority(-10) == "OVERDUE"

    def test_assign_priority_unknown(self):
        assert assign_priority(None) == "UNKNOWN"

    def test_calculate_confidence_score(self):
        row = pd.Series({
            "contract_end": datetime(2027, 1, 1),
            "award_date": datetime(2024, 1, 1),
            "contract_value": 150000,
            "description": "A" * 150,
            "matched_cpv": "48190000-6",
        })
        score = calculate_confidence_score(row)
        assert score > 50

    def test_predict_republication_dates(self):
        df = pd.DataFrame({
            "title": ["Test tender"],
            "publication_date": [datetime(2023, 1, 1)],
            "organization": ["Test Org"],
        })
        result = predict_republication_dates(df, contract_years=3, lead_months=4)
        assert "expected_republication" in result.columns
        assert "contact_by_date" in result.columns
        assert "priority" in result.columns
        assert "days_until_contact" in result.columns

    def test_predict_republication_contract_end_direct(self):
        """Contract_end wordt DIRECT gebruikt, geen jaren toegevoegd."""
        df = pd.DataFrame({
            "title": ["Test tender"],
            "contract_end": [datetime(2027, 6, 15)],
            "publication_date": [datetime(2023, 1, 1)],
            "organization": ["Test Org"],
        })
        result = predict_republication_dates(df, contract_years=3, lead_months=4)
        # Contract_end (2027-06-15) wordt direct als republication gebruikt
        assert result["expected_republication"].iloc[0] == datetime(2027, 6, 15)
        assert result["reference_type"].iloc[0] == "Einddatum contract"

    def test_predict_republication_publication_adds_years(self):
        """Publication_date krijgt contract_years toegevoegd (budgetcyclus)."""
        df = pd.DataFrame({
            "title": ["Test tender"],
            "publication_date": [datetime(2023, 11, 15)],
            "organization": ["Test Org"],
        })
        result = predict_republication_dates(df, contract_years=3, lead_months=4)
        # 2023-11-15 + 3 jaar = 2026-11-15
        assert result["expected_republication"].iloc[0] == datetime(2026, 11, 15)
        assert result["reference_type"].iloc[0] == "Publicatiedatum"

    def test_get_priority_summary(self):
        df = pd.DataFrame({
            "priority": ["URGENT", "URGENT", "HIGH", "LOW", "UNKNOWN"],
        })
        summary = get_priority_summary(df)
        assert summary["URGENT"] == 2
        assert summary["HIGH"] == 1
        assert summary["LOW"] == 1
        assert summary["MEDIUM"] == 0


class TestSeasonalPattern:
    """Test seasonal pattern detection (Fase 3: Seizoenslogica)."""

    def test_seasonal_pattern_clear_q4(self):
        """Multiple publications in Q4 should detect Q4 pattern."""
        dates = [
            datetime(2020, 11, 15),
            datetime(2021, 10, 20),
            datetime(2023, 12, 5),
        ]
        result = get_seasonal_pattern(dates)
        assert result == "Publiceert meestal in Q4"

    def test_seasonal_pattern_clear_q1(self):
        """Multiple publications in Q1 should detect Q1 pattern."""
        dates = [
            datetime(2020, 2, 10),
            datetime(2022, 1, 15),
            datetime(2023, 3, 20),
        ]
        result = get_seasonal_pattern(dates)
        assert result == "Publiceert meestal in Q1"

    def test_seasonal_pattern_no_pattern(self):
        """Evenly spread publications should return None."""
        dates = [
            datetime(2020, 1, 15),
            datetime(2021, 4, 20),
            datetime(2022, 7, 5),
            datetime(2023, 10, 10),
        ]
        result = get_seasonal_pattern(dates)
        assert result is None

    def test_seasonal_pattern_single_date(self):
        """Single date should return None (not enough data)."""
        dates = [datetime(2023, 11, 15)]
        result = get_seasonal_pattern(dates)
        assert result is None

    def test_seasonal_pattern_empty(self):
        """Empty list should return None."""
        assert get_seasonal_pattern([]) is None
        assert get_seasonal_pattern(None) is None

    def test_seasonal_pattern_two_same_quarter(self):
        """Two dates in same quarter should detect pattern."""
        dates = [
            datetime(2020, 5, 10),
            datetime(2022, 6, 20),
        ]
        result = get_seasonal_pattern(dates)
        assert result == "Publiceert meestal in Q2"

    def test_seasonal_pattern_in_org_aggregation(self):
        """Test that publication_pattern is included in aggregate_organizations output."""
        df = pd.DataFrame({
            "title": ["LMS v1", "LMS v2", "Other"],
            "organization": ["Org A", "Org A", "Org B"],
            "organization_city": ["City", "City", "City2"],
            "publication_date": [
                datetime(2020, 11, 15),
                datetime(2022, 10, 20),
                datetime(2023, 6, 1),
            ],
            "expected_republication": [
                datetime(2025, 11, 15),
                datetime(2025, 10, 20),
                datetime(2026, 6, 1),
            ],
            "priority": ["HIGH", "HIGH", "MEDIUM"],
            "days_until_contact": [30, 45, 120],
            "contract_value": [100000, 50000, 200000],
        })
        result = aggregate_organizations(df)
        org_a = result[result["organization"] == "Org A"].iloc[0]
        assert org_a["publication_pattern"] == "Publiceert meestal in Q4"
        # Org B has only 1 tender, no pattern
        org_b = result[result["organization"] == "Org B"].iloc[0]
        assert org_b["publication_pattern"] == ""


class TestIntegration:
    """Integration tests with sample data."""

    def create_sample_data(self):
        """Create sample TenderNed-like data."""
        return pd.DataFrame({
            "Titel": [
                "LMS platform voor gemeente",
                "E-learning modules HR",
                "Wegenbouw A12",
                "Leermanagementsysteem onderwijs",
            ],
            "Omschrijving": [
                "Aanbesteding voor een learning management systeem",
                "Ontwikkeling e-learning content voor HR afdeling",
                "Onderhoud snelweg A12",
                "Nieuw LMS voor basisonderwijs",
            ],
            "Publicatiedatum": [
                "2023-01-15",
                "2023-03-20",
                "2023-06-01",
                "2022-11-10",
            ],
            "Aanbestedende_dienst": [
                "Gemeente Amsterdam",
                "Ministerie van BZK",
                "Rijkswaterstaat",
                "Stichting Onderwijs",
            ],
            "cpv_code": [
                "48190000-6",
                "80420000-4",
                "45233120-6",
                "48931000-3",
            ],
        })

    def test_full_pipeline(self):
        """Test complete data processing pipeline."""
        # Load and normalize
        df = self.create_sample_data()
        df = normalize_column_names(df)
        df = parse_dates(df)
        df = clean_text_columns(df)

        # Validate
        is_valid, issues = validate_data(df)
        assert is_valid

        # Filter
        filtered = filter_relevant_tenders(df, use_keywords=True, use_cpv=True)
        assert len(filtered) == 3  # Should exclude "Wegenbouw A12"

        # Predict
        predicted = predict_republication_dates(filtered)
        assert all(col in predicted.columns for col in [
            "expected_republication",
            "contact_by_date",
            "priority",
        ])

        # Summary
        summary = get_priority_summary(predicted)
        assert isinstance(summary, dict)


class TestAIScorer:
    """Test AI scoring module (without actual API calls)."""

    def test_anthropic_available(self):
        """Test that anthropic library is detected."""
        # Should return True if installed, False otherwise
        result = is_anthropic_available()
        assert isinstance(result, bool)

    def test_should_analyze_with_ai_basic(self):
        """Test pre-filter logic for AI analysis."""
        # Tender with keyword match should be analyzed
        tender_with_match = {
            "title": "LMS voor gemeente",
            "description": "We zoeken een e-learning platform voor onze medewerkers.",
            "matched_terms": "LMS, e-learning",
            "matched_cpv": "",
            "days_until_contact": 100,
        }
        should_analyze, reason = should_analyze_with_ai(tender_with_match)
        assert should_analyze is True
        assert reason == "OK"

    def test_should_analyze_with_ai_no_match(self):
        """Test that tenders without matches are skipped."""
        tender_no_match = {
            "title": "Wegenbouw project",
            "description": "Aanleg van snelweg",
            "matched_terms": "",
            "matched_cpv": "",
            "days_until_contact": 100,
        }
        should_analyze, reason = should_analyze_with_ai(tender_no_match)
        assert should_analyze is False
        assert "keyword" in reason.lower() or "match" in reason.lower()

    def test_should_analyze_with_ai_too_old(self):
        """Test that old tenders are skipped (> 5 years / 1825 days) via publication_date."""
        from datetime import timedelta
        old_date = datetime.now() - timedelta(days=2000)  # > 1825 dagen geleden
        old_tender = {
            "title": "LMS systeem",
            "description": "E-learning platform aanbesteding voor de hele organisatie",
            "matched_terms": "LMS, e-learning",
            "matched_cpv": "",
            "publication_date": old_date,
        }
        should_analyze, reason = should_analyze_with_ai(old_tender)
        assert should_analyze is False
        assert "oud" in reason.lower()

    def test_should_analyze_with_ai_core_competitor_skipped(self):
        """Test dat core-concurrent tenders geen AI scoring nodig hebben (al score 100)."""
        tender = {
            "title": "Wegenbouw",
            "description": "Aanleg snelweg, geen e-learning",
            "matched_terms": "",
            "matched_cpv": "",
            "keyword_score": 100,
            "match_type": "Kernconcurrent",
        }
        should_analyze, reason = should_analyze_with_ai(tender)
        assert should_analyze is False
        assert "kernconcurrent" in reason.lower() or "100" in reason

    def test_should_analyze_with_ai_short_text(self):
        """Test that tenders with too short text are skipped."""
        short_tender = {
            "title": "LMS",
            "description": "",  # Too short
            "matched_terms": "LMS",
            "matched_cpv": "",
            "days_until_contact": 100,
        }
        should_analyze, reason = should_analyze_with_ai(short_tender)
        assert should_analyze is False
        assert "tekst" in reason.lower() or "karakter" in reason.lower()

    def test_create_tender_hash(self):
        """Test that tender hashing works consistently."""
        tender = {
            "title": "Test Tender",
            "description": "Description",
            "organization": "Org",
        }
        hash1 = create_tender_hash(tender)
        hash2 = create_tender_hash(tender)
        assert hash1 == hash2

        # Different tender should have different hash
        tender2 = {
            "title": "Different Tender",
            "description": "Description",
            "organization": "Org",
        }
        hash3 = create_tender_hash(tender2)
        assert hash1 != hash3

    def test_parse_ai_response_valid(self):
        """Test parsing valid AI response."""
        response = '''{"relevance_score": 75, "explanation": "Good match", "best_product": "Inspire", "sector_match": "Overheid", "confidence": "Hoog"}'''
        result = parse_ai_response(response)
        assert result["relevance_score"] == 75
        assert result["best_product"] == "Inspire"
        assert result["confidence"] == "Hoog"

    def test_parse_ai_response_with_markdown(self):
        """Test parsing AI response wrapped in markdown."""
        response = '''```json
{"relevance_score": 60, "explanation": "Moderate match", "best_product": "Create", "sector_match": "Onderwijs", "confidence": "Medium"}
```'''
        result = parse_ai_response(response)
        assert result["relevance_score"] == 60
        assert result["best_product"] == "Create"

    def test_parse_ai_response_invalid(self):
        """Test parsing invalid AI response."""
        response = "This is not JSON"
        result = parse_ai_response(response)
        assert result["relevance_score"] == 0
        assert result.get("error") is True

    def test_parse_ai_response_score_bounds(self):
        """Test that scores are bounded to 0-100."""
        response = '{"relevance_score": 150, "explanation": "test", "best_product": "None", "sector_match": "None", "confidence": "Low"}'
        result = parse_ai_response(response)
        assert result["relevance_score"] == 100  # Capped at 100

        response2 = '{"relevance_score": -50, "explanation": "test", "best_product": "None", "sector_match": "None", "confidence": "Low"}'
        result2 = parse_ai_response(response2)
        assert result2["relevance_score"] == 0  # Minimum is 0

    def test_get_skillstown_context(self):
        """Test that context generation works."""
        context = get_skillstown_context()
        assert "SkillsTown" in context
        assert "Inspire" in context
        assert "Create" in context
        assert "overheid" in context.lower()

    def test_create_scoring_prompt(self):
        """Test prompt creation."""
        tender = {
            "title": "LMS Aanbesteding",
            "description": "We zoeken een online leerplatform",
            "organization": "Gemeente Utrecht",
            "cpv_codes": "48190000-6",
            "matched_terms": "LMS, leerplatform",
        }
        prompt = create_scoring_prompt(tender)
        assert "LMS Aanbesteding" in prompt
        assert "Gemeente Utrecht" in prompt
        assert "JSON" in prompt

    def test_get_ai_summary_empty(self):
        """Test AI summary with no analyzed tenders."""
        df = pd.DataFrame({
            "title": ["Test"],
            "ai_analyzed": [False],
            "ai_score": [None],
        })
        summary = get_ai_summary(df)
        assert summary["total_analyzed"] == 0

    def test_get_ai_summary_with_data(self):
        """Test AI summary with analyzed tenders."""
        df = pd.DataFrame({
            "title": ["Test1", "Test2", "Test3"],
            "ai_analyzed": [True, True, False],
            "ai_score": [80, 40, None],
            "ai_product": ["Inspire", "Create", None],
            "ai_sector": ["Overheid", "Onderwijs", None],
        })
        summary = get_ai_summary(df)
        assert summary["total_analyzed"] == 2
        assert summary["avg_score"] == 60.0
        assert summary["high_relevance"] == 1  # score >= 60
        assert summary["medium_relevance"] == 1  # 40 <= score < 60


class TestOrgAnalyzer:
    """Test organization-level analysis for sales call list."""

    def _create_predicted_df(self):
        """Create sample predicted DataFrame for org tests."""
        return pd.DataFrame({
            "title": ["LMS platform", "E-learning modules", "LMS upgrade"],
            "organization": ["Gemeente Amsterdam", "Gemeente Amsterdam", "Ministerie BZK"],
            "organization_city": ["Amsterdam", "Amsterdam", "Den Haag"],
            "publication_date": [
                datetime(2022, 11, 15),
                datetime(2023, 3, 20),
                datetime(2023, 6, 1),
            ],
            "expected_republication": [
                datetime(2025, 11, 15),
                datetime(2026, 3, 20),
                datetime(2026, 6, 1),
            ],
            "priority": ["OVERDUE", "HIGH", "MEDIUM"],
            "days_until_contact": [-60, 45, 120],
            "competitor_win": ["GoodHabitz", "", "StudyTube"],
            "contract_value": [100000, 50000, 200000],
        })

    def test_get_quarter_label(self):
        assert get_quarter_label(datetime(2026, 1, 15)) == "Q1 2026"
        assert get_quarter_label(datetime(2026, 6, 1)) == "Q2 2026"
        assert get_quarter_label(datetime(2026, 9, 30)) == "Q3 2026"
        assert get_quarter_label(datetime(2026, 12, 31)) == "Q4 2026"

    def test_get_quarter_label_nan(self):
        assert get_quarter_label(pd.NaT) == ""

    def test_get_quarter_sort_key(self):
        assert get_quarter_sort_key("Q1 2026") == 20261
        assert get_quarter_sort_key("Q4 2025") < get_quarter_sort_key("Q1 2026")
        assert get_quarter_sort_key("") == 999999

    def test_aggregate_organizations_groups_correctly(self):
        df = self._create_predicted_df()
        result = aggregate_organizations(df)
        # Should group into 2 organizations
        assert len(result) == 2
        orgs = result["organization"].tolist()
        assert "Gemeente Amsterdam" in orgs
        assert "Ministerie BZK" in orgs

    def test_aggregate_organizations_amsterdam_details(self):
        df = self._create_predicted_df()
        result = aggregate_organizations(df)
        amsterdam = result[result["organization"] == "Gemeente Amsterdam"].iloc[0]
        assert amsterdam["city"] == "Amsterdam"
        assert amsterdam["tender_count"] == 2
        assert amsterdam["total_contract_value"] == 150000
        assert "GoodHabitz" in amsterdam["competitors_won"]

    def test_aggregate_organizations_priority(self):
        """Best (most urgent) priority from group should be used."""
        df = self._create_predicted_df()
        result = aggregate_organizations(df)
        amsterdam = result[result["organization"] == "Gemeente Amsterdam"].iloc[0]
        # OVERDUE is more urgent than HIGH
        assert amsterdam["priority"] == "OVERDUE"

    def test_aggregate_organizations_empty(self):
        result = aggregate_organizations(pd.DataFrame())
        assert result.empty

    def test_aggregate_organizations_sorted_by_warmth(self):
        df = self._create_predicted_df()
        result = aggregate_organizations(df)
        # First org should have highest warmth score
        warmth_scores = result["warmth_score"].tolist()
        assert warmth_scores == sorted(warmth_scores, reverse=True)

    def test_get_organizations_to_contact_filters_priority(self):
        df = self._create_predicted_df()
        org_df = aggregate_organizations(df)
        result = get_organizations_to_contact(org_df, priorities=["OVERDUE"])
        assert all(row["priority"] == "OVERDUE" for _, row in result.iterrows())

    def test_get_organizations_to_contact_filters_days(self):
        df = self._create_predicted_df()
        org_df = aggregate_organizations(df)
        result = get_organizations_to_contact(
            org_df, max_days=30, priorities=["OVERDUE", "URGENT", "HIGH", "MEDIUM", "LOW"]
        )
        for _, row in result.iterrows():
            if pd.notna(row["days_until_contact"]):
                assert row["days_until_contact"] <= 30

    def test_get_organization_summary(self):
        df = self._create_predicted_df()
        org_df = aggregate_organizations(df)
        summary = get_organization_summary(org_df)
        assert summary["total_organizations"] == 2
        assert summary["with_competitor_intel"] >= 1
        assert summary["total_contract_value"] == 350000

    def test_get_organization_summary_empty(self):
        summary = get_organization_summary(pd.DataFrame())
        assert summary["total_organizations"] == 0

    def test_export_call_list(self):
        df = self._create_predicted_df()
        org_df = aggregate_organizations(df)
        call_list = export_call_list(org_df)
        assert "Organisatie" in call_list.columns
        assert "Jaren geleden" in call_list.columns
        assert "Verwachte herpublicatie" in call_list.columns
        assert len(call_list) == len(org_df)

    def test_export_call_list_empty(self):
        result = export_call_list(pd.DataFrame())
        assert result.empty


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
