"""
Data loading and validation for TenderNed Excel files.
Handles various column naming conventions and data formats.
"""

import pandas as pd
from typing import Optional
import streamlit as st


# Known column name mappings for TenderNed data
# Maps various possible column names to standardized names
COLUMN_MAPPINGS = {
    # Publication/tender ID
    "id": "tender_id",
    "ocid": "tender_id",
    "tender_id": "tender_id",
    "aanbesteding_id": "tender_id",
    "publicatie_id": "tender_id",
    "id_publicatie": "tender_id",
    "tenderned_kenmerk": "tenderned_id",

    # Title
    "title": "title",
    "titel": "title",
    "naam": "title",
    "onderwerp": "title",
    "tender_title": "title",
    "naam_aanbesteding": "title",

    # Description
    "description": "description",
    "omschrijving": "description",
    "beschrijving": "description",
    "tender_description": "description",
    "omschrijving_aanbesteding": "description",
    "perceel_beschrijving": "lot_description",
    "perceel_titel": "lot_title",

    # Publication date
    "publisheddate": "publication_date",
    "published_date": "publication_date",
    "publicatiedatum": "publication_date",
    "datum_publicatie": "publication_date",
    "date": "publication_date",
    "datum": "publication_date",

    # Contracting authority
    "tender_procuringentity_name": "organization",
    "procuringentity_name": "organization",
    "aanbestedende_dienst": "organization",
    "organisatie": "organization",
    "opdrachtgever": "organization",
    "buyer_name": "organization",
    "buyer": "organization",
    "naam_aanbestedende_dienst": "organization",
    "officiële_naam_aanbestedende_dienst": "organization_official",

    # Organization address/location
    "tender_procuringentity_address_locality": "organization_city",
    "plaats": "organization_city",
    "city": "organization_city",
    "locality": "organization_city",
    "ad_plaats": "organization_city",

    # CPV codes
    "tender_items_classification_id": "cpv_codes",
    "cpv_code": "cpv_codes",
    "cpv_codes": "cpv_codes",
    "cpv": "cpv_codes",
    "classification_id": "cpv_codes",
    "hoofd_cpv_code": "cpv_codes",
    "hoofd_cpv_omschrijving": "cpv_description",
    "perceel_cpv_code": "lot_cpv_codes",

    # Award date
    "awards_date": "award_date",
    "award_date": "award_date",
    "gunningsdatum": "award_date",
    "datum_gunning": "award_date",

    # Contract value
    "awards_value_amount": "contract_value",
    "contract_value": "contract_value",
    "waarde": "contract_value",
    "bedrag": "contract_value",
    "value_amount": "contract_value",
    "value": "contract_value",
    "definitieve_waarde___bedrag": "contract_value",
    "oorspronkelijk_geraamde_waarde___bedrag": "estimated_value",

    # Currency
    "awards_value_currency": "currency",
    "currency": "currency",
    "valuta": "currency",
    "definitieve_waarde___valuta": "currency",

    # Contract period
    "contracts_period_startdate": "contract_start",
    "contract_start": "contract_start",
    "startdatum": "contract_start",
    "ingangsdatum": "contract_start",
    "aanvang_opdracht": "contract_start",

    "contracts_period_enddate": "contract_end",
    "contract_end": "contract_end",
    "einddatum": "contract_end",
    "voltooiing_opdracht": "contract_end",

    # Procedure type
    "tender_procurementmethod": "procedure_type",
    "procurement_method": "procedure_type",
    "procedure": "procedure_type",
    "procedure_type": "procedure_type",
    "type_procedure": "procedure_type",

    # Status
    "status": "status",
    "tender_status": "status",
    "publicatie_soort": "publication_type",
    "publicatie_type": "tender_type",

    # Winning company (for competitor analysis!)
    "naam_gegunde_onderneming": "winning_company",
    "on_kvknummer": "winning_company_kvk",
    "on_plaats": "winning_company_city",

    # Additional useful fields
    "url_tenderned": "tender_url",
    "trefwoorden": "keywords",
    "aantal_inschrijvingen": "num_bids",
    "soort_aanbestedende_dienst": "organization_type",
    "nationaal_of_europees": "tender_scope",
}

# Required columns for analysis
REQUIRED_COLUMNS = ["title", "publication_date", "organization"]


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize column names to standard format.
    Handles various naming conventions from TenderNed data.
    """
    # Convert all column names to lowercase and replace spaces/dots with underscores
    df.columns = df.columns.str.lower().str.replace(" ", "_").str.replace(".", "_")

    # Create mapping for actual columns found
    rename_map = {}
    for col in df.columns:
        col_clean = col.lower().strip()
        if col_clean in COLUMN_MAPPINGS:
            rename_map[col] = COLUMN_MAPPINGS[col_clean]

    # Apply renaming
    df = df.rename(columns=rename_map)

    return df


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse date columns to datetime format.
    Handles various date formats including ISO and European.
    """
    date_columns = [
        "publication_date",
        "award_date",
        "contract_start",
        "contract_end",
    ]

    # Common date formats to try
    date_formats = [
        "%Y-%m-%d",      # ISO: 2024-01-15
        "%d-%m-%Y",      # European: 15-01-2024
        "%Y/%m/%d",      # Slash ISO: 2024/01/15
        "%d/%m/%Y",      # Slash European: 15/01/2024
        "%Y-%m-%dT%H:%M:%S",  # ISO with time
    ]

    for col in date_columns:
        if col in df.columns:
            # Try to infer format first, then fall back to manual parsing
            parsed = pd.to_datetime(df[col], errors="coerce", format="mixed", dayfirst=True)
            df[col] = parsed

    return df


def clean_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean text columns by stripping whitespace and handling missing values.
    """
    text_columns = [
        "title", "description", "organization", "cpv_codes",
        "lot_title", "lot_description", "winning_company", "keywords",
        "cpv_description"
    ]

    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    return df


def validate_data(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """
    Validate that required columns are present and data is usable.
    Returns (is_valid, list of issues).
    """
    issues = []

    # Check for required columns
    missing_cols = []
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            missing_cols.append(col)

    if missing_cols:
        issues.append(f"Ontbrekende kolommen: {', '.join(missing_cols)}")

    # Check for data
    if len(df) == 0:
        issues.append("Geen data gevonden in bestand")

    # Check for valid dates
    if "publication_date" in df.columns:
        valid_dates = df["publication_date"].notna().sum()
        if valid_dates == 0:
            issues.append("Geen geldige publicatiedatums gevonden")
        elif valid_dates < len(df) * 0.5:
            issues.append(
                f"Waarschuwing: slechts {valid_dates} van {len(df)} rijen hebben geldige datums"
            )

    is_valid = len([i for i in issues if not i.startswith("Waarschuwing")]) == 0
    return is_valid, issues


def _normalize_col(col: str) -> str:
    """Normalize a column name to match COLUMN_MAPPINGS keys."""
    return col.lower().strip().replace(" ", "_").replace(".", "_")


def _build_usecols_filter() -> set:
    """Build set of normalized column names we want to keep."""
    return set(COLUMN_MAPPINGS.keys())


def _get_parquet_cache_path(xlsx_path: str) -> Optional[str]:
    """Return parquet cache path for an xlsx file, or None if path is not a local file."""
    try:
        from pathlib import Path
        p = Path(xlsx_path)
        if p.exists():
            return str(p.with_suffix(".parquet"))
    except Exception:
        pass
    return None


def _parquet_cache_valid(xlsx_path: str, parquet_path: str) -> bool:
    """Return True if parquet cache exists and is newer than the xlsx file."""
    try:
        from pathlib import Path
        p_xlsx = Path(xlsx_path)
        p_parquet = Path(parquet_path)
        return p_parquet.exists() and p_parquet.stat().st_mtime >= p_xlsx.stat().st_mtime
    except Exception:
        return False


@st.cache_data(show_spinner=False)
def load_tenderned_data(uploaded_file) -> Optional[pd.DataFrame]:
    """
    Load and process TenderNed Excel data.

    Args:
        uploaded_file: Streamlit UploadedFile object, of een string bestandspad

    Returns:
        Processed DataFrame or None if loading fails
    """
    try:
        # Check parquet cache EERST (local files only) — slaat xlsx-parsing volledig over
        parquet_path = _get_parquet_cache_path(uploaded_file) if isinstance(uploaded_file, str) else None
        if parquet_path and _parquet_cache_valid(uploaded_file, parquet_path):
            st.info("Dataset geladen uit cache (snel).")
            df = pd.read_parquet(parquet_path)
            df = parse_dates(df)
            df["row_number"] = range(1, len(df) + 1)
            return df

        # Determine engine: calamine is much faster (Rust-based), fall back to openpyxl
        try:
            import python_calamine  # noqa: F401
            engine = "calamine"
        except ImportError:
            engine = "openpyxl"

        # Check available sheets (openpyxl needed for sheet listing)
        xlsx = pd.ExcelFile(uploaded_file, engine="openpyxl")
        sheet_names = xlsx.sheet_names

        # Determine which sheet to read
        data_sheet = None
        for name in sheet_names:
            name_lower = name.lower()
            if "opendata" in name_lower or "data" in name_lower:
                data_sheet = name
                break
            if "leeswijzer" not in name_lower and "mapping" not in name_lower:
                data_sheet = name

        if data_sheet is None:
            if len(sheet_names) > 1 and "leeswijzer" in sheet_names[0].lower():
                data_sheet = sheet_names[1]
            else:
                data_sheet = sheet_names[0]

        st.info(f"Laden van sheet: '{data_sheet}' (engine: {engine}) — eerste keer kan even duren...")

        # Only load columns we actually use — reduces load time significantly
        known_cols = _build_usecols_filter()
        usecols = lambda col: _normalize_col(col) in known_cols  # noqa: E731

        # Read Excel file — only relevant columns
        df = pd.read_excel(
            uploaded_file,
            sheet_name=data_sheet,
            engine=engine,
            usecols=usecols,
        )

        # Normalize column names
        df = normalize_column_names(df)

        # Parse dates
        df = parse_dates(df)

        # Clean text columns
        df = clean_text_columns(df)

        # Add row index for reference
        df["row_number"] = range(1, len(df) + 1)

        # Sla op als parquet cache voor snelle volgende laadbeurt (alleen lokale bestanden)
        if parquet_path:
            try:
                df.to_parquet(parquet_path, index=False)
            except Exception:
                pass  # Cache mislukken is niet erg

        return df

    except Exception as e:
        st.error(f"Fout bij laden van bestand: {str(e)}")
        return None


def get_column_info(df: pd.DataFrame) -> dict:
    """
    Get information about available columns for debugging.
    """
    return {
        "total_columns": len(df.columns),
        "columns": list(df.columns),
        "total_rows": len(df),
        "date_columns_found": [
            col
            for col in ["publication_date", "award_date", "contract_start", "contract_end"]
            if col in df.columns
        ],
        "text_columns_found": [
            col
            for col in ["title", "description", "organization", "cpv_codes"]
            if col in df.columns
        ],
    }
