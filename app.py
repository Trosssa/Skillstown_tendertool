"""
SkillsTown TenderNed Analyzer
Data-analyse tool voor het analyseren van aanbestedingen uit TenderNed.
"""

import streamlit as st
import pandas as pd

# --- Wachtwoordbeveiliging ---
def check_password():
    if st.session_state.get("authenticated"):
        return True
    pw = st.text_input("Wachtwoord", type="password", key="login_pw")
    if st.button("Inloggen"):
        if pw == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Ongeldig wachtwoord")
    return False

if not check_password():
    st.stop()
from io import BytesIO
from pathlib import Path
from typing import Optional

from src.config import (
    SEARCH_TERMS,
    CPV_CODES,
    ALL_CPV_CODES,
    CPV_DESCRIPTIONS,
    DEFAULT_CONTRACT_YEARS,
    DEFAULT_LEAD_MONTHS,
    NEGATIVE_KEYWORDS,
    COMPETITORS,
    CORE_COMPETITORS,
    AI_CONFIG,
    LOCAL_DATASET_PATTERN,
)
from src.data_loader import load_tenderned_data, validate_data, get_column_info
from src.org_analyzer import export_call_list
from src.ai_scorer import (
    is_anthropic_available,
    score_tenders_batch,
    get_ai_summary,
    filter_by_ai_score,
    should_analyze_with_ai,
    apply_cached_scores,
)

# Page config
st.set_page_config(
    page_title="SkillsTown TenderNed Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS - SkillsTown brand style
st.markdown("""
<style>
    /* SkillsTown branding: dark, professional, minimalist */
    .metric-card { padding: 1rem; margin-bottom: 1rem; border: 1px solid #e0e0e0; }

    /* Header styling */
    header[data-testid="stHeader"] {
        background-color: #000000;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #f5f5f5;
        color: #1a1a1a;
    }
    section[data-testid="stSidebar"] .stMarkdown { color: #1a1a1a; }
    section[data-testid="stSidebar"] label { color: #333333 !important; }
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 { color: #000000; }
    section[data-testid="stSidebar"] .stDivider { border-color: #d0d0d0; }

    /* Button styling */
    .stButton > button {
        background-color: #000000;
        color: #ffffff;
        border: 1px solid #333333;
        border-radius: 0px;
    }
    .stButton > button:hover {
        background-color: #1a1a1a;
        color: #ffffff;
        border: 1px solid #555555;
    }

    /* Download button */
    .stDownloadButton > button {
        background-color: #000000;
        color: #ffffff;
        border: 1px solid #333333;
        border-radius: 0px;
    }

    /* Tabs styling */
    .stTabs [data-baseweb="tab"] {
        color: #100717;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        border-bottom-color: #000000;
    }

    /* Metric containers */
    [data-testid="stMetric"] {
        border: 1px solid #e0e0e0;
        padding: 12px;
        background-color: #fafafa;
    }
    [data-testid="stMetricLabel"] {
        color: #100717;
    }

    /* Clean font styling */
    h1, h2, h3 { color: #000000; font-weight: 600; }
    .stMarkdown p { color: #100717; }
</style>
""", unsafe_allow_html=True)


COLUMN_EXPLANATIONS = {
    "AI Score": (
        "Score van 0-100 door Claude AI (Haiku model). Geeft aan hoe relevant deze tender is voor SkillsTown. "
        "100 = gewonnen door directe concurrent. Primaire sorteervolgorde."
    ),
    "AI Toelichting": (
        "Uitleg van de AI over waarom deze tender relevant of irrelevant is. "
        "Gebaseerd op titel, omschrijving, CPV-code en winnende partij."
    ),
    "Organisatie": "Naam van de aanbestedende dienst (opdrachtgever). Oorspronkelijke TenderNed veld: naam_aanbestedende_dienst.",
    "Titel": "Naam/onderwerp van de aanbesteding zoals gepubliceerd op TenderNed. Veld: naam_aanbesteding.",
    "Omschrijving": (
        "Vrije tekstomschrijving van de opdracht zoals de aanbestedende dienst die heeft gepubliceerd. "
        "Veld: omschrijving_aanbesteding. Basis voor AI scoring en keyword matching."
    ),
    "Gegund aan (concurrent)": (
        "Bedrijf dat de opdracht gewonnen heeft. Veld: naam_gegunde_onderneming. "
        "Kernconcurrenten (Plusport, GoodHabitz, etc.) geven automatisch AI Score 100."
    ),
    "Herpublicatie verwacht": (
        "Geschatte datum waarop de organisatie opnieuw gaat aanbesteden. "
        "Zie kolom 'Basis herpublicatie' voor hoe dit berekend is."
    ),
    "Basis herpublicatie": (
        "Hoe de herpublicatiedatum berekend is. Twee mogelijkheden: "
        "(1) 'Einddatum contract: ...' = exacte einddatum bekend uit TenderNed, geen schatting. "
        "(2) 'Publicatiedatum ... + X jaar contractduur' = schatting op basis van aangenomen contractduur."
    ),
    "Contractwaarde": "Definitieve contractwaarde in euro's zoals opgegeven bij gunning. Veld: definitieve_waarde___bedrag.",
    "Geraamde waarde": "Door de aanbestedende dienst geraamde waarde vóór gunning. Veld: oorspronkelijk_geraamde_waarde___bedrag.",
    "Publicatiedatum": (
        "Datum waarop de aanbesteding gepubliceerd is op TenderNed. "
        "Basis voor herpublicatieschatting en datumfilter in de app. Veld: publicatiedatum."
    ),
    "Perceel omschrijving": "Omschrijving van een specifiek perceel (onderdeel) van de aanbesteding. Veld: perceel_beschrijving.",
    "Gevonden termen": "Zoektermen uit de SkillsTown-woordenlijst die gevonden zijn in titel/omschrijving (keyword matching).",
    "Keyword score": "Gewogen score op basis van gevonden zoektermen (LMS=5, e-learning=4, blended=3, etc.). Schaal 0-100.",
    "Contract start": "Startdatum van het gegunde contract. Veld: aanvang_opdracht.",
    "Contract eind": "Einddatum van het gegunde contract. Als ingevuld: wordt direct gebruikt als herpublicatiedatum (geen schatting). Veld: voltooiing_opdracht.",
    "Gunningsdatum": "Datum waarop de opdracht officieel gegund is aan de winnende partij. Veld: gunningsdatum.",
    "Aantal inschrijvingen": "Aantal partijen dat heeft ingeschreven op de aanbesteding. Veld: aantal_inschrijvingen.",
    "Soort organisatie": "Type aanbestedende dienst (gemeente, provincie, rijksoverheid, zorg, etc.). Veld: soort_aanbestedende_dienst.",
    "Organisatie plaats": "Vestigingsplaats van de aanbestedende dienst. Veld: ad_plaats.",
    "Gegund aan (plaats)": "Vestigingsplaats van de winnende partij. Veld: on_plaats.",
    "CPV code": "Europese productclassificatiecode (Common Procurement Vocabulary). Veld: hoofd_cpv_code.",
    "CPV omschrijving": "Omschrijving behorend bij de CPV-code. Veld: hoofd_cpv_omschrijving.",
    "Procedure type": "Type aanbestedingsprocedure (openbaar, niet-openbaar, onderhandeling, etc.). Veld: type_procedure.",
    "Nationaal/Europees": "Of de aanbesteding nationaal of Europees (boven drempelwaarde) is gepubliceerd. Veld: nationaal_of_europees.",
    "TenderNed URL": "Directe link naar de aanbesteding op TenderNed.nl. Veld: url_tenderned.",
}


def export_to_excel(df: pd.DataFrame) -> BytesIO:
    """Export DataFrame to Excel file with explanation sheet."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        export_df = df.copy()

        date_cols = ["publication_date", "award_date", "contract_start", "contract_end",
                     "reference_date", "expected_republication", "contact_by_date",
                     "Publicatiedatum", "Gunningsdatum", "Contract start", "Contract eind",
                     "Herpublicatie verwacht"]
        for col in date_cols:
            if col in export_df.columns:
                export_df[col] = pd.to_datetime(export_df[col], errors="coerce").dt.date

        export_df.to_excel(writer, sheet_name="Tenders", index=False)

        worksheet = writer.sheets["Tenders"]
        for i, col in enumerate(export_df.columns):
            max_len = max(export_df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, min(max_len, 50))

        # Werkblad 2: uitleg per kolom
        legend_rows = []
        for col in export_df.columns:
            legend_rows.append({
                "Kolom": col,
                "Uitleg": COLUMN_EXPLANATIONS.get(col, "—"),
            })
        legend_df = pd.DataFrame(legend_rows)
        legend_df.to_excel(writer, sheet_name="Uitleg kolommen", index=False)

        legend_ws = writer.sheets["Uitleg kolommen"]
        legend_ws.set_column(0, 0, 30)   # Kolom-naam kolom
        legend_ws.set_column(1, 1, 80)   # Uitleg kolom

    output.seek(0)
    return output


def format_value(value) -> str:
    """Format contract value for display."""
    if pd.isna(value) or value == 0:
        return "-"
    return f"EUR {value:,.0f}"


def format_years(years) -> str:
    """Format years since publication."""
    if pd.isna(years):
        return "-"
    return f"{years:.1f} jaar"


@st.cache_data(show_spinner=False)
def process_tenders(_df, use_keywords, use_cpv, filter_negatives, contract_years, lead_months):
    """Cache the heavy processing pipeline. Only reruns when inputs change."""
    from src.filters import filter_relevant_tenders, add_match_details, filter_out_negative_keywords, detect_competitor_wins, get_competitor_summary
    from src.predictor import predict_republication_dates

    # Filter relevant tenders
    filtered_df = filter_relevant_tenders(_df, use_keywords=use_keywords, use_cpv=use_cpv)
    filtered_df = add_match_details(filtered_df)
    negatives_removed = 0
    if filter_negatives:
        before_count = len(filtered_df)
        filtered_df = filter_out_negative_keywords(filtered_df)
        negatives_removed = before_count - len(filtered_df)

    # Deduplicate
    dedup_removed = 0
    if "publication_date" in filtered_df.columns:
        before_dedup = len(filtered_df)
        filtered_df = filtered_df.sort_values("publication_date", ascending=False)
        filtered_df = filtered_df.drop_duplicates(subset=["organization", "title"], keep="first")
        dedup_removed = before_dedup - len(filtered_df)

    # Competitor analysis (on full dataset)
    df_with_competitors = detect_competitor_wins(_df)
    competitor_summary = get_competitor_summary(df_with_competitors)

    # Predictions
    predicted_df = predict_republication_dates(filtered_df, contract_years=contract_years, lead_months=lead_months)

    return predicted_df, df_with_competitors, competitor_summary, negatives_removed, dedup_removed


@st.cache_data(show_spinner=False)
def aggregate_orgs(_predicted_df, contract_years, lead_months):
    """Cache organization aggregation."""
    from src.org_analyzer import aggregate_organizations, get_organization_summary
    org_df = aggregate_organizations(_predicted_df, contract_years, lead_months)
    org_summary = get_organization_summary(org_df)
    return org_df, org_summary


def find_local_dataset() -> Optional[Path]:
    """
    Zoek naar de lokale TenderNed dataset in de app-map.
    Geeft het meest recente bestand terug als er meerdere zijn.
    """
    app_dir = Path(__file__).parent
    matches = sorted(app_dir.glob(LOCAL_DATASET_PATTERN), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


@st.cache_data(show_spinner=False)
def load_local_dataset(file_path: str) -> Optional[pd.DataFrame]:
    """Laad de lokale dataset via bestandspad (gecached)."""
    return load_tenderned_data(file_path)


def main():
    # Header
    st.title("SkillsTown TenderNed Analyzer")
    st.markdown("Analyseer relevante aanbestedingen uit TenderNed data.")

    # Sidebar
    with st.sidebar:
        st.header("Instellingen")

        # Data sectie: auto-load of upload
        st.subheader("Data")
        local_dataset = find_local_dataset()
        uploaded_file = None

        if local_dataset:
            st.success(f"Lokale dataset gevonden: `{local_dataset.name}`")
            use_local = st.checkbox("Gebruik lokale dataset", value=True)
            with st.expander("Of upload een andere dataset"):
                uploaded_file = st.file_uploader(
                    "Upload TenderNed Excel",
                    type=["xlsx", "xls"],
                    help="Overschrijft de lokale dataset",
                )
            if use_local and uploaded_file is None:
                uploaded_file = str(local_dataset)  # str-pad voor cache-key
        else:
            uploaded_file = st.file_uploader(
                "Upload TenderNed Excel",
                type=["xlsx", "xls"],
                help="Upload een Excel export van TenderNed",
            )

        st.divider()

        # Filter settings
        st.subheader("Filters")
        use_keywords = st.checkbox("Filter op zoektermen", value=True)
        use_cpv = st.checkbox("Filter op CPV codes", value=True)
        filter_negatives = st.checkbox(
            "Vacatures uitsluiten",
            value=True,
            help="Sluit tenders uit die vacature-gerelateerde woorden bevatten"
        )

        with st.expander("Zoektermen"):
            st.write(", ".join(SEARCH_TERMS))
        with st.expander("CPV codes"):
            for category, codes in CPV_CODES.items():
                st.markdown(f"**{category.replace('_', ' ').title()}**")
                for code in codes:
                    desc = CPV_DESCRIPTIONS.get(code, "")
                    st.markdown(f"- `{code}`: {desc}")
        with st.expander("Uitgesloten woorden"):
            st.write(", ".join(NEGATIVE_KEYWORDS))
        with st.expander("Bekende concurrenten"):
            st.write(", ".join(COMPETITORS[:15]) + "...")

        st.divider()

        # Datum filter (breed, achtergrondfilter)
        st.divider()
        st.subheader("Datum filter")
        st.caption("Verwachte herpublicatie (publicatiedatum + contractduur)")
        date_filter_enabled = st.checkbox(
            "Filter op verwachte herpublicatie",
            value=True,
            help="Toon alleen tenders waarbij heruitgifte binnen het opgegeven bereik valt",
        )
        if date_filter_enabled:
            date_range = st.slider(
                "Bereik (jaren t.o.v. nu)",
                min_value=-1,
                max_value=5,
                value=(-1, 5),
                help="Van 1 jaar geleden tot 5 jaar in de toekomst",
            )
        else:
            date_range = (-999, 999)

        # Voorspelling instellingen (technisch, in expander)
        with st.expander("Voorspelling instellingen"):
            st.caption("Basis voor geschatte herpublicatiedatum")
            contract_years = st.slider(
                "Verwachte contractduur (jaren)",
                min_value=1,
                max_value=10,
                value=DEFAULT_CONTRACT_YEARS,
                help="Aangenomen duur van contracten",
            )
            lead_months = st.slider(
                "Lead time (maanden voor contact)",
                min_value=1,
                max_value=12,
                value=DEFAULT_LEAD_MONTHS,
                help="Maanden vóór verwachte herpublicatie dat je contact opneemt",
            )

        # AI Scoring sectie
        st.divider()
        st.subheader("AI Scoring")
        with st.expander("AI Relevantie Scoring (Claude Haiku)"):
            ai_enabled = st.checkbox(
                "AI scoring inschakelen",
                value=False,
                help="Claude Haiku beoordeelt elke tender op relevantie (0-100). ~€0.10 per 1000 tenders."
            )

            api_key = ""
            ai_min_score = 30

            if ai_enabled:
                if not is_anthropic_available():
                    st.warning("Anthropic library niet geinstalleerd. Run: `pip install anthropic`")
                    ai_enabled = False
                else:
                    # Gebruik API key uit Streamlit secrets (Streamlit Cloud) als die beschikbaar is
                    secret_key = st.secrets.get("ANTHROPIC_API_KEY", "") if hasattr(st, "secrets") else ""
                    if secret_key:
                        api_key = secret_key
                        st.info("API key geladen uit configuratie.", icon="🔑")
                    else:
                        api_key = st.text_input(
                            "Anthropic API Key",
                            type="password",
                            help="Je API key van console.anthropic.com"
                        )
                    ai_min_score = st.slider(
                        "Minimum AI relevantie score",
                        min_value=0,
                        max_value=100,
                        value=AI_CONFIG.get("relevance_threshold", 30),
                        help="Tenders onder deze score worden gefilterd",
                    )

    # Main content
    if uploaded_file is None:
        st.info("Geen dataset gevonden. Upload een TenderNed Excel bestand via de sidebar om te beginnen.")

        st.markdown("""
        ### Wat doet deze tool?
        - **Filtert** relevante aanbestedingen op zoektermen en CPV codes
        - **Groepeert** resultaten per organisatie voor overzicht
        - **Toont** welke organisaties eerder relevante tenders uitschreven
        - **Analyseert** concurrentie: welke partijen wonnen eerdere opdrachten
        - **Schat in** wanneer contracten mogelijk verlopen (optioneel)

        ### Hoe te gebruiken
        1. Plaats de TenderNed Excel in de app-map, of upload via de sidebar
        2. Bekijk de analyse per organisatie, tender of concurrent
        3. Exporteer resultaten naar Excel
        """)
        return

    # Load data — ondersteunt zowel lokaal pad (str) als geüpload bestand
    with st.spinner("Data laden..."):
        if isinstance(uploaded_file, str):
            df = load_local_dataset(uploaded_file)
        else:
            df = load_tenderned_data(uploaded_file)

    if df is None:
        st.error("Kon het bestand niet laden. Controleer of het een geldig Excel bestand is.")
        return

    # Validate
    is_valid, issues = validate_data(df)
    for issue in issues:
        if issue.startswith("Waarschuwing"):
            st.warning(issue)
        else:
            st.error(issue)

    if not is_valid:
        st.error("Data validatie mislukt.")
        with st.expander("Kolom informatie"):
            st.json(get_column_info(df))
        return

    # Process all heavy computations (cached)
    with st.spinner("Data verwerken..."):
        predicted_df, df_with_competitors, competitor_summary, negatives_removed, dedup_removed = \
            process_tenders(df, use_keywords, use_cpv, filter_negatives, contract_years, lead_months)

    # Datum filter toepassen (brede achtergrondfilter)
    if date_filter_enabled and "expected_republication" in predicted_df.columns:
        from datetime import date
        today = pd.Timestamp.now()
        min_date = today + pd.DateOffset(years=date_range[0])
        max_date = today + pd.DateOffset(years=date_range[1])

        # Behoud ook tenders zonder verwachte herpublicatie (we sluiten ze niet uit)
        date_mask = (
            predicted_df["expected_republication"].isna() |
            (
                (predicted_df["expected_republication"] >= min_date) &
                (predicted_df["expected_republication"] <= max_date)
            )
        )
        before_date = len(predicted_df)
        predicted_df = predicted_df[date_mask].copy()
        date_filtered = before_date - len(predicted_df)
        if date_filtered > 0:
            st.info(f"{date_filtered} tenders buiten herpublicatie-bereik gefilterd ({date_range[0]:+d} tot {date_range[1]:+d} jaar)")

    if negatives_removed > 0:
        st.info(f"{negatives_removed} vacature-gerelateerde tenders uitgefilterd")
    if dedup_removed > 0:
        st.info(f"{dedup_removed} dubbele tenders verwijderd (zelfde titel + organisatie)")

    # Laad gecachede AI scores (ook zonder API key)
    predicted_df = apply_cached_scores(predicted_df)
    ai_scored = "ai_score" in predicted_df.columns and predicted_df["ai_score"].notna().any()

    # AI Scoring (if enabled)
    if ai_enabled and api_key:
        if "ai_cache" not in st.session_state:
            st.session_state.ai_cache = {}

        needs_analysis = sum(
            1 for _, row in predicted_df.iterrows()
            if should_analyze_with_ai(row.to_dict())[0]
        )

        if needs_analysis > 0:
            st.info(f"{needs_analysis} tenders komen in aanmerking voor AI analyse")

            if st.button(f"Start AI Scoring ({needs_analysis} tenders)", type="primary"):
                progress_bar = st.progress(0)
                status_text = st.empty()

                def update_progress(current, total, title):
                    progress_bar.progress(current / total)
                    status_text.text(f"Analyseren {current}/{total}: {title[:50]}...")

                with st.spinner("AI analyse uitvoeren..."):
                    predicted_df = score_tenders_batch(
                        predicted_df,
                        api_key=api_key,
                        cache=st.session_state.ai_cache,
                        progress_callback=update_progress,
                    )
                    ai_scored = True

                progress_bar.empty()
                status_text.empty()

                ai_summary = get_ai_summary(predicted_df)
                st.success(f"AI analyse voltooid: {ai_summary['total_analyzed']} geanalyseerd, "
                          f"gemiddelde score: {ai_summary['avg_score']}%")

        ai_scored = "ai_score" in predicted_df.columns and predicted_df["ai_score"].notna().any()

    # Summary metrics
    st.header("Overzicht")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Totaal in dataset", f"{len(df):,}")
    with col2:
        st.metric("Relevante tenders", f"{len(predicted_df):,}")
    with col3:
        # Unique organizations
        org_count = predicted_df["organization"].nunique() if "organization" in predicted_df.columns else 0
        st.metric("Unieke organisaties", org_count)

    # Aggregate organizations (cached)
    with st.spinner("Organisaties aggregeren..."):
        org_df, org_summary = aggregate_orgs(predicted_df, contract_years, lead_months)

    # Tabs
    tab_tenders, tab_org, tab_comp, tab_timeline, tab_info = st.tabs([
        "Tenders", "Organisaties", "Concurrentie", "Tijdlijn", "Data Info"
    ])

    # ==================== TAB: ORGANISATIES ====================
    with tab_org:
        st.subheader("Analyse per organisatie")
        st.markdown("Organisaties gesorteerd op relevantie. Klik op een organisatie voor details.")

        # Methodology explanation
        with st.expander("Hoe werkt de relevantiescore?"):
            st.markdown(f"""
            De **relevantiescore** (0-100) is gebaseerd op **gewogen keyword-matching**:

            | Factor | Gewicht | Voorbeelden |
            |--------|---------|-------------|
            | Kernconcurrent als winnaar | **100** (override) | Plusport, GoodHabitz, StudyTube... |
            | Kern producttermen | 5 | LMS, LXP, leerplatform, e-learning bibliotheek |
            | Sterk relevante termen | 4 | E-learning, online leren, auteurstool |
            | Relevante termen | 3 | Blended learning, SCORM, leerportaal |
            | Contextuele termen | 2 | Webinar, microlearning, compliance training |
            | Zwakke signalen | 1 | Management training, persoonlijke ontwikkeling |

            Frequentie telt mee: een tender die 3x "LMS" noemt scoort hoger dan één vermelding.

            **Geschatte herpublicatie:**
            - Als contract einddatum bekend → direct gebruikt
            - Anders: publicatiedatum + {contract_years} jaar
            - Dit is een indicatie, geen exacte voorspelling

            **Datum filter** in de sidebar bepaalt welke tenders zichtbaar zijn (standaard: -1 tot +5 jaar).
            """)

        if org_df.empty:
            st.info("Geen organisaties gevonden in de gefilterde data.")
        else:
            # Summary
            org_col1, org_col2, org_col3 = st.columns(3)
            with org_col1:
                st.metric("Organisaties", org_summary["total_organizations"])
            with org_col2:
                st.metric("Met concurrent-info", org_summary["with_competitor_intel"])
            with org_col3:
                total_val = org_summary["total_contract_value"]
                st.metric("Totale contractwaarde", format_value(total_val) if total_val > 0 else "-")

            st.divider()

            # Filters
            filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
            with filter_col1:
                min_score = st.number_input(
                    "Minimum relevantie",
                    min_value=0,
                    max_value=100,
                    value=0,
                    step=5,
                    help="Toon alleen organisaties met relevantiescore >= dit getal",
                )
            with filter_col2:
                repub_filter = st.selectbox(
                    "Verwachte herpublicatie",
                    options=[
                        "Alle",
                        "2025",
                        "2026",
                        "Q1 2026", "Q2 2026", "Q3 2026", "Q4 2026",
                        "2027",
                        "Q1 2027", "Q2 2027", "Q3 2027", "Q4 2027",
                        "2028+",
                        "Onbekend",
                    ],
                    index=0,
                    help="Filter organisaties op verwachte herpublicatie periode",
                )
            with filter_col3:
                search_org = st.text_input(
                    "Zoek organisatie",
                    placeholder="Typ om te filteren...",
                )
            with filter_col4:
                min_years = st.number_input(
                    "Min. jaren geleden",
                    min_value=0.0,
                    max_value=15.0,
                    value=0.0,
                    step=0.5,
                    help="Optioneel: filter op jaren sinds laatste publicatie",
                )

            # Apply filters
            display_org_df = org_df.copy()
            if min_score > 0:
                display_org_df = display_org_df[display_org_df["relevance_score"] >= min_score]
            if min_years > 0:
                display_org_df = display_org_df[
                    (display_org_df["years_since_publication"].notna()) &
                    (display_org_df["years_since_publication"] >= min_years)
                ]
            if search_org:
                display_org_df = display_org_df[
                    display_org_df["organization"].str.contains(search_org, case=False, na=False)
                ]

            # Herpublicatie filter
            if repub_filter != "Alle":
                if repub_filter == "Onbekend":
                    display_org_df = display_org_df[
                        display_org_df["expected_republication_quarter"] == ""
                    ]
                elif repub_filter == "2028+":
                    display_org_df = display_org_df[
                        display_org_df["expected_republication"].notna() &
                        (display_org_df["expected_republication"].apply(
                            lambda x: x.year >= 2028 if pd.notna(x) else False
                        ))
                    ]
                elif repub_filter in ("2025", "2026", "2027"):
                    year = int(repub_filter)
                    display_org_df = display_org_df[
                        display_org_df["expected_republication"].notna() &
                        (display_org_df["expected_republication"].apply(
                            lambda x: x.year == year if pd.notna(x) else False
                        ))
                    ]
                else:
                    # Quarter filter like "Q3 2026"
                    display_org_df = display_org_df[
                        display_org_df["expected_republication_quarter"] == repub_filter
                    ]

            # Main table
            org_display_cols = [
                "relevance_score",
                "organization",
                "city",
                "years_since_publication",
                "last_publication_date",
                "expected_republication_quarter",
                "competitors_won",
                "total_contract_value",
                "tender_count",
                "publication_pattern",
            ]
            org_display_cols = [c for c in org_display_cols if c in display_org_df.columns]

            org_column_names = {
                "relevance_score": "Relevantie",
                "organization": "Organisatie",
                "city": "Plaats",
                "years_since_publication": "Jaren geleden",
                "last_publication_date": "Laatste publicatie",
                "expected_republication_quarter": "Geschatte herpublicatie",
                "competitors_won": "Eerdere leveranciers",
                "total_contract_value": "Contractwaarde",
                "tender_count": "Tenders",
                "publication_pattern": "Seizoenspatroon",
            }

            display_org_formatted = display_org_df.copy()
            if "total_contract_value" in display_org_formatted.columns:
                display_org_formatted["total_contract_value"] = display_org_formatted["total_contract_value"].apply(
                    lambda x: format_value(x)
                )
            if "last_publication_date" in display_org_formatted.columns:
                display_org_formatted["last_publication_date"] = pd.to_datetime(
                    display_org_formatted["last_publication_date"]
                ).dt.strftime("%Y-%m-%d")

            st.dataframe(
                display_org_formatted[org_display_cols].rename(columns=org_column_names),
                use_container_width=True,
                height=400,
            )
            st.caption(f"Toont {len(display_org_df)} van {len(org_df)} organisaties")

            # Detail view per organization
            st.divider()
            st.subheader("Details per organisatie")

            for _, org_row in display_org_df.head(50).iterrows():
                org_name = org_row["organization"]
                years = org_row.get("years_since_publication")
                score = org_row.get("relevance_score", 0)
                label = f"[{score}] {org_name}"
                if org_row.get("city"):
                    label += f" ({org_row['city']})"
                label += f" — {format_years(years)}"
                comp = org_row.get("competitors_won", "")
                if comp:
                    label += f" | Leverancier: {comp}"

                with st.expander(label):
                    info_cols = st.columns(4)
                    with info_cols[0]:
                        pub_date = org_row.get("last_publication_date")
                        st.metric("Laatste publicatie",
                                  pub_date.strftime("%Y-%m-%d") if pd.notna(pub_date) else "-")
                    with info_cols[1]:
                        repub_q = org_row.get("expected_republication_quarter", "")
                        st.metric("Geschatte herpublicatie", repub_q if repub_q else "-")
                    with info_cols[2]:
                        val = org_row.get("total_contract_value", 0)
                        st.metric("Contractwaarde", format_value(val))
                    with info_cols[3]:
                        st.metric("Eerdere leveranciers", comp if comp else "Onbekend")

                    # Relevance explanation
                    explanation = org_row.get("relevance_explanation", "")
                    if explanation:
                        st.markdown(f"**Relevantiescore ({score}/100):** {explanation}")

                    # Republication basis
                    repub_basis = org_row.get("republication_basis", "")
                    if repub_basis:
                        st.caption(f"Basis herpublicatie-schatting: {repub_basis}")

                    pattern = org_row.get("publication_pattern", "")
                    if pattern:
                        st.info(f"Seizoenspatroon: {pattern}")

                    # Underlying tenders with full context
                    org_tenders = predicted_df[predicted_df["organization"] == org_name].copy()
                    if not org_tenders.empty:
                        tender_cols = ["title", "publication_date", "contract_value",
                                       "expected_republication", "republication_basis",
                                       "match_type", "winning_company", "cpv_codes"]
                        tender_cols = [c for c in tender_cols if c in org_tenders.columns]
                        tender_names = {
                            "title": "Tender",
                            "publication_date": "Publicatiedatum",
                            "contract_value": "Waarde",
                            "expected_republication": "Geschatte herpublicatie",
                            "republication_basis": "Basis schatting",
                            "match_type": "Match type",
                            "winning_company": "Gegund aan",
                            "cpv_codes": "CPV code",
                        }
                        st.dataframe(
                            org_tenders[tender_cols].rename(columns=tender_names),
                            use_container_width=True,
                            hide_index=True,
                        )

                        # Show descriptions per tender
                        for idx_t, tender_row in org_tenders.iterrows():
                            desc = tender_row.get("description", "")
                            lot_desc = tender_row.get("lot_description", "")
                            full_desc = str(desc) if pd.notna(desc) and str(desc).strip() else ""
                            if pd.notna(lot_desc) and str(lot_desc).strip():
                                full_desc = f"{full_desc}\n\n{lot_desc}" if full_desc else str(lot_desc)
                            if full_desc and full_desc != "nan":
                                title = str(tender_row.get("title", ""))[:80]
                                if len(full_desc) > 300:
                                    with st.expander(f"Omschrijving: {title}"):
                                        st.markdown(full_desc)
                                else:
                                    st.markdown(f"**{title}**")
                                    st.caption(full_desc)

            # Export
            st.divider()
            call_list = export_call_list(display_org_df)
            if not call_list.empty:
                call_list_excel = BytesIO()
                with pd.ExcelWriter(call_list_excel, engine="xlsxwriter") as writer:
                    call_list.to_excel(writer, sheet_name="Analyse", index=False)
                    worksheet = writer.sheets["Analyse"]
                    for i, col in enumerate(call_list.columns):
                        max_len = max(call_list[col].astype(str).map(len).max(), len(col)) + 2
                        worksheet.set_column(i, i, min(max_len, 50))
                call_list_excel.seek(0)

                st.download_button(
                    label="Exporteer analyse naar Excel",
                    data=call_list_excel,
                    file_name="skillstown_analyse_organisaties.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

    # ==================== TAB: TENDERS ====================
    with tab_tenders:
        st.subheader("Alle relevante tenders")

        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            search_tender = st.text_input(
                "Zoek in titel/organisatie",
                placeholder="Typ om te filteren...",
                key="tender_search",
            )
        with filter_col2:
            if ai_scored and "ai_score" in predicted_df.columns:
                ai_score_filter = st.slider(
                    "Min AI score",
                    min_value=0,
                    max_value=100,
                    value=ai_min_score,
                )
            else:
                ai_score_filter = 0

        display_df = predicted_df.copy()

        if search_tender:
            mask = (
                display_df["title"].str.contains(search_tender, case=False, na=False) |
                display_df["organization"].str.contains(search_tender, case=False, na=False)
            )
            display_df = display_df[mask]

        if ai_scored and "ai_score" in display_df.columns and ai_score_filter > 0:
            display_df = display_df[
                (display_df["ai_score"].isna()) |
                (display_df["ai_score"] >= ai_score_filter)
            ]

        # Sortering: AI score primair (als beschikbaar), anders keyword_score, dan publicatiedatum
        if ai_scored and "ai_score" in display_df.columns and display_df["ai_score"].notna().any():
            display_df = display_df.sort_values(
                ["ai_score", "keyword_score", "publication_date"],
                ascending=[False, False, False],
                na_position="last",
            )
        elif "keyword_score" in display_df.columns:
            display_df = display_df.sort_values(
                ["keyword_score", "publication_date"],
                ascending=[False, False],
                na_position="last",
            )
        else:
            display_df = display_df.sort_values("publication_date", ascending=False, na_position="last")

        # Select columns
        display_columns = [
            "organization",
            "title",
            "publication_date",
            "expected_republication",
            "match_type",
        ]

        if ai_scored and "ai_score" in display_df.columns:
            display_columns.append("ai_score")
            display_columns.append("ai_explanation")

        display_columns = [c for c in display_columns if c in display_df.columns]

        column_names = {
            "organization": "Organisatie",
            "title": "Titel",
            "publication_date": "Publicatiedatum",
            "expected_republication": "Geschatte herpublicatie",
            "match_type": "Match type",
            "ai_score": "AI Score",
            "ai_explanation": "AI Uitleg",
        }

        st.dataframe(
            display_df[display_columns].rename(columns=column_names),
            use_container_width=True,
            height=400,
        )
        st.caption(f"Toont {len(display_df)} van {len(predicted_df)} tenders")

        st.divider()

        # Export — gebruik display_df zodat AI score filter en zoekfilter meegenomen worden

        # Tenders zonder AI score krijgen een label en worden uitgesloten van export
        export_source = display_df.copy()
        if ai_scored and "ai_score" in export_source.columns:
            no_score_mask = export_source["ai_score"].isna()
            export_source.loc[no_score_mask, "ai_explanation"] = "Onvoldoende input data"
            export_source = export_source[~no_score_mask]

        export_cols = [
            # Blok 1: Waarom relevant
            "ai_score", "ai_explanation",
            # Blok 2: De kans
            "organization", "title", "description",
            "winning_company",
            "expected_republication", "republication_basis",
            # Blok 3: Context
            "contract_value", "estimated_value",
            "publication_date", "lot_description",
            # Blok 4: Details
            "matched_terms", "keyword_score",
            "contract_start", "contract_end", "award_date",
            "num_bids",
            # Blok 5: Achtergrondinformatie
            "organization_type", "organization_city",
            "winning_company_city",
            "cpv_codes", "cpv_description",
            "procedure_type", "tender_scope",
            "tender_url",
        ]
        export_cols = [c for c in export_cols if c in export_source.columns]

        export_rename = {
            "ai_score": "AI Score",
            "ai_explanation": "AI Toelichting",
            "organization": "Organisatie",
            "title": "Titel",
            "description": "Omschrijving",
            "winning_company": "Gegund aan (concurrent)",
            "expected_republication": "Herpublicatie verwacht",
            "republication_basis": "Basis herpublicatie",
            "contract_value": "Contractwaarde",
            "estimated_value": "Geraamde waarde",
            "publication_date": "Publicatiedatum",
            "lot_description": "Perceel omschrijving",
            "matched_terms": "Gevonden termen",
            "keyword_score": "Keyword score",
            "contract_start": "Contract start",
            "contract_end": "Contract eind",
            "award_date": "Gunningsdatum",
            "num_bids": "Aantal inschrijvingen",
            "organization_type": "Soort organisatie",
            "organization_city": "Organisatie plaats",
            "winning_company_city": "Gegund aan (plaats)",
            "cpv_codes": "CPV code",
            "cpv_description": "CPV omschrijving",
            "procedure_type": "Procedure type",
            "tender_scope": "Nationaal/Europees",
            "tender_url": "TenderNed URL",
        }

        export_df = export_source[export_cols].rename(columns=export_rename)
        export_df = export_df.sort_values("AI Score", ascending=False, na_position="last")
        export_data = export_to_excel(export_df)
        st.download_button(
            label="Exporteer tenders naar Excel (gefilterde data)",
            data=export_data,
            file_name="skillstown_analyse_tenders.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ==================== TAB: CONCURRENTIE ====================
    with tab_comp:
        st.subheader("Concurrentie analyse")

        core_names = list(CORE_COMPETITORS.keys())
        st.markdown(
            f"Tenders gewonnen door concurrenten. "
            f"**Kernconcurrenten** (maximale leads): {', '.join(core_names)}"
        )

        if competitor_summary:
            import plotly.express as px

            # Kleur: kernconcurrenten donker, overige grijs
            comp_df = pd.DataFrame([
                {
                    "Concurrent": k,
                    "Aantal opdrachten": v,
                    "Type": "Kernconcurrent" if k in core_names else "Overig",
                }
                for k, v in competitor_summary.items()
            ])

            fig = px.bar(
                comp_df,
                x="Concurrent",
                y="Aantal opdrachten",
                color="Type",
                color_discrete_map={"Kernconcurrent": "#000000", "Overig": "#999999"},
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)

            # Kernconcurrenten apart uitlichten
            competitor_tenders = df_with_competitors[df_with_competitors["is_competitor_win"] == True].copy()
            if len(competitor_tenders) > 0:
                core_mask = competitor_tenders.get(
                    "is_core_competitor_win",
                    competitor_tenders["competitor_win"].isin(core_names)
                )
                core_tenders = competitor_tenders[core_mask]
                if len(core_tenders) > 0:
                    st.markdown(f"### Kernconcurrenten — {len(core_tenders)} opdrachten")
                    st.caption("Dit zijn de sterkste leads: contract loopt af, organisatie gaat opnieuw aanbesteden.")
                    comp_display_cols = ["organization", "title", "winning_company",
                                         "competitor_win", "publication_date", "contract_value"]
                    comp_display_cols = [c for c in comp_display_cols if c in core_tenders.columns]
                    comp_column_names = {
                        "organization": "Opdrachtgever", "title": "Opdracht",
                        "winning_company": "Winnaar (exact)", "competitor_win": "Concurrent",
                        "publication_date": "Publicatiedatum", "contract_value": "Waarde",
                    }
                    sort_col = "publication_date" if "publication_date" in core_tenders.columns else comp_display_cols[0]
                    st.dataframe(
                        core_tenders[comp_display_cols].sort_values(sort_col, ascending=False).rename(columns=comp_column_names),
                        use_container_width=True,
                        height=350,
                    )

                st.markdown("### Alle concurrenten-opdrachten")
                comp_display_cols = ["organization", "title", "winning_company", "competitor_win", "publication_date"]
                comp_display_cols = [c for c in comp_display_cols if c in competitor_tenders.columns]
                comp_column_names = {
                    "organization": "Opdrachtgever", "title": "Opdracht",
                    "winning_company": "Winnaar", "competitor_win": "Concurrent",
                    "publication_date": "Datum",
                }
                st.dataframe(
                    competitor_tenders[comp_display_cols].rename(columns=comp_column_names).head(200),
                    use_container_width=True,
                    height=400,
                )
                st.caption(f"Toont {min(200, len(competitor_tenders))} van {len(competitor_tenders)} concurrent-opdrachten")
            else:
                st.info("Geen opdrachten gevonden die naar concurrenten gingen")
        else:
            st.info("Geen concurrentie-data beschikbaar. Mogelijk ontbreekt de kolom 'Naam gegunde onderneming' in de data.")

    # ==================== TAB: TIJDLIJN ====================
    with tab_timeline:
        st.subheader("Tenders over tijd")
        st.markdown("Verdeling van relevante tenders per periode.")

        if not predicted_df.empty and "publication_date" in predicted_df.columns:
            import plotly.express as px

            timeline_df = predicted_df[predicted_df["publication_date"].notna()].copy()
            timeline_df["jaar"] = timeline_df["publication_date"].dt.year

            # Tenders per year
            yearly = timeline_df.groupby("jaar").size().reset_index(name="Aantal tenders")

            fig = px.bar(
                yearly,
                x="jaar",
                y="Aantal tenders",
                title="Relevante tenders per jaar",
                color_discrete_sequence=["#000000"],
            )
            fig.update_layout(xaxis_title="Jaar", yaxis_title="Aantal")
            st.plotly_chart(fig, use_container_width=True)

            # Expected republications (if available)
            repub_df = predicted_df[predicted_df["expected_republication"].notna()].copy()
            if not repub_df.empty:
                repub_df["expected_republication"] = pd.to_datetime(repub_df["expected_republication"], errors="coerce")
                repub_df["repub_jaar"] = repub_df["expected_republication"].dt.year
                repub_yearly = repub_df.groupby("repub_jaar").size().reset_index(name="Aantal")

                st.markdown("### Geschatte herpublicaties per jaar")
                st.caption("Op basis van aangenomen contractduur — ter indicatie, niet als exacte voorspelling.")

                fig2 = px.bar(
                    repub_yearly,
                    x="repub_jaar",
                    y="Aantal",
                    color_discrete_sequence=["#404040"],
                )
                fig2.update_layout(xaxis_title="Jaar", yaxis_title="Aantal")
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Geen data beschikbaar voor tijdlijn")

    # ==================== TAB: DATA INFO ====================
    with tab_info:
        st.subheader("Data informatie")

        col_info = get_column_info(df)

        st.markdown("**Geladen kolommen:**")
        st.write(", ".join(col_info["columns"]))

        st.markdown("**Gevonden datumvelden:**")
        st.write(", ".join(col_info["date_columns_found"]) or "Geen")

        st.markdown("**Gevonden tekstvelden:**")
        st.write(", ".join(col_info["text_columns_found"]) or "Geen")

        st.divider()

        st.markdown("**Ruwe data preview (eerste 10 rijen):**")
        st.dataframe(df.head(10), use_container_width=True)


if __name__ == "__main__":
    main()
