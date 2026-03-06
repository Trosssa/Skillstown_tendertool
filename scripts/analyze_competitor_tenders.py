"""
Concurrenten-tenders analyse script voor SkillsTown TenderNed Analyzer.

Wat doet dit script?
1. Laadt de lokale TenderNed dataset (Dataset_Tenderned*.xlsx)
2. Extraheert alle tenders gewonnen door de 7 kernconcurrenten
3. Analyseert patronen: CPV-codes, titels, organisaties, sectoren
4. Exporteert resultaten naar:
   - scripts/output/competitor_tenders.json   (ruwe data)
   - scripts/output/competitor_analysis.txt   (leesbare samenvatting)
5. Optioneel: gebruikt Claude AI voor diepere analyse van de omschrijvingen
   (output kan worden toegevoegd aan SKILLSTOWN_CONTEXT_DOCUMENT.md)

Gebruik:
    python scripts/analyze_competitor_tenders.py
    python scripts/analyze_competitor_tenders.py --ai   (met AI analyse, vereist ANTHROPIC_API_KEY)

Vereisten:
    pip install pandas openpyxl anthropic python-dotenv
"""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

# Windows console: forceer UTF-8 output zodat Nederlandse tekens geen crash geven
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd

# Voeg project root toe aan sys.path zodat src imports werken
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import CORE_COMPETITORS, ALL_CORE_COMPETITOR_TERMS, LOCAL_DATASET_PATTERN
from src.filters import is_core_competitor_win, detect_competitor_wins
from src.data_loader import normalize_column_names, parse_dates, clean_text_columns

OUTPUT_DIR = Path(__file__).parent / "output"


def find_dataset() -> Optional[Path]:
    """Zoek naar de lokale TenderNed dataset."""
    matches = sorted(
        PROJECT_ROOT.glob(LOCAL_DATASET_PATTERN),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def load_dataset(path: Path) -> Optional[pd.DataFrame]:
    """Laad de TenderNed dataset."""
    print(f"Dataset laden: {path.name} ({path.stat().st_size / 1024 / 1024:.1f} MB)...")

    try:
        xlsx = pd.ExcelFile(path, engine="openpyxl")
        sheet_names = xlsx.sheet_names
        print(f"Sheets gevonden: {sheet_names}")

        # Kies het data-sheet
        data_sheet = None
        for name in sheet_names:
            name_lower = name.lower()
            if "opendata" in name_lower or ("data" in name_lower and "leeswijzer" not in name_lower):
                data_sheet = name
                break
        if data_sheet is None:
            # Pak het eerste non-leeswijzer sheet
            for name in sheet_names:
                if "leeswijzer" not in name.lower():
                    data_sheet = name
                    break
        if data_sheet is None:
            data_sheet = sheet_names[0]

        print(f"Data laden uit sheet: '{data_sheet}'...")
        df = pd.read_excel(path, sheet_name=data_sheet, engine="openpyxl")
        print(f"Geladen: {len(df):,} rijen, {len(df.columns)} kolommen")

        df = normalize_column_names(df)
        df = parse_dates(df)
        df = clean_text_columns(df)

        return df

    except Exception as e:
        print(f"Fout bij laden: {e}")
        return None


def extract_competitor_tenders(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extraheer alle tenders die gewonnen zijn door de 7 kernconcurrenten.
    """
    if "winning_company" not in df.columns:
        print("FOUT: kolom 'winning_company' niet gevonden. Controleer column mapping.")
        print(f"Beschikbare kolommen: {list(df.columns)[:20]}...")
        return pd.DataFrame()

    print("\nZoeken naar tenders van kernconcurrenten...")

    # Voeg kolommen toe
    df_work = df.copy()
    df_work["matched_competitor"] = ""
    df_work["is_core_win"] = False

    matches = []
    for idx, row in df_work.iterrows():
        company = str(row.get("winning_company", ""))
        is_core, name = is_core_competitor_win(company)
        if is_core:
            df_work.at[idx, "matched_competitor"] = name
            df_work.at[idx, "is_core_win"] = True
            matches.append(idx)

    competitor_tenders = df_work.loc[matches].copy()
    print(f"Gevonden: {len(competitor_tenders):,} tenders van kernconcurrenten")

    # Per concurrent
    for name in CORE_COMPETITORS.keys():
        count = (competitor_tenders["matched_competitor"] == name).sum()
        print(f"  - {name}: {count} tenders")

    return competitor_tenders


def analyze_patterns(df: pd.DataFrame) -> dict:
    """
    Analyseer patronen in de concurrenten-tenders:
    - Meest voorkomende CPV-codes
    - Meest voorkomende titeltermen
    - Organisaties die meerdere keren bij een concurrent aanbestedden
    - Contractwaarden
    - Sectoren
    """
    analysis = {}

    # === CPV codes ===
    cpv_counts = Counter()
    if "cpv_codes" in df.columns:
        for cpv_str in df["cpv_codes"].dropna():
            # CPV codes kunnen komma-gescheiden zijn
            codes = [c.strip() for c in str(cpv_str).split(",") if c.strip()]
            cpv_counts.update(codes)

    analysis["top_cpv_codes"] = cpv_counts.most_common(20)

    # === Titeltermen ===
    title_words = Counter()
    if "title" in df.columns:
        stop_words = {
            "de", "het", "een", "van", "voor", "en", "in", "op", "met",
            "aan", "te", "is", "zijn", "het", "of", "naar", "door",
            "tot", "bij", "als", "om", "dat", "die", "dit", "werd",
            "worden", "wordt", "niet", "ook", "aan", "uit", "over",
        }
        for title in df["title"].dropna():
            words = str(title).lower().split()
            for word in words:
                word_clean = word.strip(".,;:()[]\"'")
                if len(word_clean) > 3 and word_clean not in stop_words:
                    title_words[word_clean] += 1

    analysis["top_title_words"] = title_words.most_common(30)

    # === Organisaties ===
    if "organization" in df.columns:
        org_counts = df.groupby("organization").size().sort_values(ascending=False)
        analysis["top_organizations"] = org_counts.head(20).to_dict()

        # Organisaties die bij meerdere concurrenten aanbestedden
        multi_competitor_orgs = (
            df.groupby("organization")["matched_competitor"]
            .apply(lambda x: list(set(x)))
            .to_dict()
        )
        analysis["organizations_multiple_competitors"] = {
            org: comps
            for org, comps in multi_competitor_orgs.items()
            if len(comps) > 1
        }

    # === Per concurrent ===
    analysis["per_competitor"] = {}
    for competitor in CORE_COMPETITORS.keys():
        subset = df[df["matched_competitor"] == competitor]
        if len(subset) == 0:
            continue

        cpv_sub = Counter()
        if "cpv_codes" in subset.columns:
            for cpv_str in subset["cpv_codes"].dropna():
                codes = [c.strip() for c in str(cpv_str).split(",") if c.strip()]
                cpv_sub.update(codes)

        values = []
        if "contract_value" in subset.columns:
            values = subset["contract_value"].dropna().tolist()

        # Jaartal distributie
        years = []
        if "publication_date" in subset.columns:
            years = [
                d.year for d in pd.to_datetime(subset["publication_date"], errors="coerce").dropna()
            ]

        analysis["per_competitor"][competitor] = {
            "count": len(subset),
            "top_cpv": cpv_sub.most_common(10),
            "avg_value": round(sum(values) / len(values)) if values else None,
            "max_value": round(max(values)) if values else None,
            "years": dict(Counter(years)),
            "organizations": subset["organization"].value_counts().head(10).to_dict()
            if "organization" in subset.columns else {},
            "sample_titles": subset["title"].dropna().head(10).tolist()
            if "title" in subset.columns else [],
        }

    # === Contractwaarden totaal ===
    if "contract_value" in df.columns:
        values = df["contract_value"].dropna()
        if len(values) > 0:
            analysis["contract_values"] = {
                "count": len(values),
                "avg": round(values.mean()),
                "median": round(values.median()),
                "min": round(values.min()),
                "max": round(values.max()),
            }

    # === Publicatiejaren ===
    if "publication_date" in df.columns:
        years = [
            d.year for d in pd.to_datetime(df["publication_date"], errors="coerce").dropna()
        ]
        analysis["publication_years"] = dict(sorted(Counter(years).items()))

    return analysis


def format_analysis_report(df: pd.DataFrame, analysis: dict) -> str:
    """
    Formatteer de analyse als leesbaar tekstrapport.
    Dit wordt later toegevoegd aan SKILLSTOWN_CONTEXT_DOCUMENT.md.
    """
    lines = []
    lines.append("=" * 70)
    lines.append("CONCURRENTEN-TENDERS ANALYSE RAPPORT")
    lines.append(f"Gegenereerd op basis van TenderNed dataset 2016-2025")
    lines.append("=" * 70)
    lines.append("")

    lines.append(f"TOTAAL: {len(df):,} tenders gewonnen door de 7 kernconcurrenten")
    lines.append("")

    # Per concurrent
    lines.append("─" * 50)
    lines.append("AANTALLEN PER CONCURRENT")
    lines.append("─" * 50)
    for competitor, data in analysis.get("per_competitor", {}).items():
        lines.append(f"\n{competitor}: {data['count']} tenders")
        if data.get("avg_value"):
            lines.append(f"  Gem. contractwaarde: EUR {data['avg_value']:,}")
        if data.get("max_value"):
            lines.append(f"  Max contractwaarde: EUR {data['max_value']:,}")
        if data.get("years"):
            year_str = ", ".join(f"{y}: {c}" for y, c in sorted(data["years"].items()))
            lines.append(f"  Jaren: {year_str}")
        if data.get("top_cpv"):
            cpv_str = ", ".join(c for c, _ in data["top_cpv"][:5])
            lines.append(f"  Top CPV: {cpv_str}")
        if data.get("organizations"):
            top_orgs = list(data["organizations"].keys())[:5]
            lines.append(f"  Top organisaties: {', '.join(top_orgs)}")
        if data.get("sample_titles"):
            lines.append("  Voorbeeldtitels:")
            for t in data["sample_titles"][:3]:
                lines.append(f"    - {t}")

    # Top CPV codes overall
    lines.append("")
    lines.append("─" * 50)
    lines.append("TOP CPV-CODES (alle concurrenten)")
    lines.append("─" * 50)
    for code, count in analysis.get("top_cpv_codes", [])[:15]:
        lines.append(f"  {code}: {count}x")

    # Top titeltermen
    lines.append("")
    lines.append("─" * 50)
    lines.append("MEEST VOORKOMENDE TITELWOORDEN")
    lines.append("─" * 50)
    top_words = analysis.get("top_title_words", [])[:20]
    lines.append("  " + ", ".join(f"{w} ({c}x)" for w, c in top_words))

    # Top organisaties
    lines.append("")
    lines.append("─" * 50)
    lines.append("TOP ORGANISATIES (meeste concurrenten-tenders)")
    lines.append("─" * 50)
    for org, count in list(analysis.get("top_organizations", {}).items())[:15]:
        lines.append(f"  {org}: {count}x")

    # Organisaties bij meerdere concurrenten
    multi = analysis.get("organizations_multiple_competitors", {})
    if multi:
        lines.append("")
        lines.append("─" * 50)
        lines.append("ORGANISATIES DIE BIJ MEERDERE CONCURRENTEN AANBESTEDDEN")
        lines.append("─" * 50)
        for org, comps in list(multi.items())[:10]:
            lines.append(f"  {org}: {', '.join(comps)}")

    # Contractwaarden
    cv = analysis.get("contract_values", {})
    if cv:
        lines.append("")
        lines.append("─" * 50)
        lines.append("CONTRACTWAARDEN")
        lines.append("─" * 50)
        lines.append(f"  Aantal tenders met waarde: {cv['count']}")
        lines.append(f"  Gemiddeld: EUR {cv['avg']:,}")
        lines.append(f"  Mediaan: EUR {cv['median']:,}")
        lines.append(f"  Range: EUR {cv['min']:,} – EUR {cv['max']:,}")

    # Publicatiejaren
    years = analysis.get("publication_years", {})
    if years:
        lines.append("")
        lines.append("─" * 50)
        lines.append("PUBLICATIEJAREN")
        lines.append("─" * 50)
        for year, count in sorted(years.items()):
            bar = "█" * min(count, 40)
            lines.append(f"  {year}: {bar} ({count})")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def run_ai_analysis(df: pd.DataFrame, api_key: str) -> str:
    """
    Gebruik Claude om de concurrenten-tenders dieper te analyseren.
    Geeft een tekst terug die kan worden toegevoegd aan SKILLSTOWN_CONTEXT_DOCUMENT.md.
    """
    try:
        import anthropic
    except ImportError:
        return "Anthropic library niet geïnstalleerd. Run: pip install anthropic"

    # Stel een representatieve sample samen: max 50 tenders, spread over concurrenten
    sample_parts = []
    for competitor in CORE_COMPETITORS.keys():
        subset = df[df["matched_competitor"] == competitor]
        sample = subset.head(10)
        for _, row in sample.iterrows():
            title = str(row.get("title", ""))[:200]
            desc = str(row.get("description", ""))[:300]
            cpv = str(row.get("cpv_codes", ""))
            sample_parts.append(
                f"[{competitor}] Titel: {title}\nCPV: {cpv}\nOmschrijving: {desc}\n"
            )

    sample_text = "\n---\n".join(sample_parts[:50])

    prompt = f"""Je bent een expert in Nederlandse publieke aanbestedingen voor e-learning en HR-tech.

Hieronder staan aanbestedingen die gewonnen zijn door directe concurrenten van SkillsTown
(een Nederlandse aanbieder van LMS/e-learning platforms: Inspire, Create, GetSpecialized).

De concurrenten zijn: {', '.join(CORE_COMPETITORS.keys())}

TENDERS:
{sample_text}

Analyseer deze tenders en geef een beknopte analyse (max 400 woorden) met:
1. Wat zijn de meest kenmerkende omschrijvingen/titels? Welke termen komen steeds terug?
2. Welke sectoren/organisatietypen besteden het meest aan bij deze concurrenten?
3. Wat zijn typische kenmerken van aanbestedingen die SkillsTown zou kunnen winnen?
4. Welke extra zoektermen of CPV-codes zouden waardevol zijn om op te filteren?
5. Zijn er patronen in contractomvang of looptijd?

Schrijf in het Nederlands. Focus op bruikbare inzichten voor de sales van SkillsTown."""

    print("\nAI analyse uitvoeren met Claude Sonnet...")
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def save_outputs(df: pd.DataFrame, analysis: dict, report: str, ai_analysis: str = "") -> None:
    """Sla alle outputs op."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Ruwe data als JSON
    json_path = OUTPUT_DIR / "competitor_tenders.json"
    export_cols = ["matched_competitor", "organization", "title", "description",
                   "cpv_codes", "publication_date", "contract_value", "winning_company"]
    export_cols = [c for c in export_cols if c in df.columns]
    export_df = df[export_cols].copy()

    # Datums serialiseerbaar maken
    for col in export_df.select_dtypes(include=["datetime64[ns]"]).columns:
        export_df[col] = export_df[col].dt.strftime("%Y-%m-%d")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(export_df.to_dict(orient="records"), f, ensure_ascii=False, indent=2)
    print(f"\nRuwe data opgeslagen: {json_path}")

    # 2. Analyse rapport als tekstbestand
    report_path = OUTPUT_DIR / "competitor_analysis.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
        if ai_analysis:
            f.write("\n\n" + "=" * 70 + "\n")
            f.write("AI ANALYSE (Claude Sonnet)\n")
            f.write("=" * 70 + "\n\n")
            f.write(ai_analysis)
    print(f"Analyse rapport opgeslagen: {report_path}")

    # 3. Excel export voor handmatige review
    excel_path = OUTPUT_DIR / "competitor_tenders.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df[export_cols].to_excel(writer, sheet_name="Concurrenten tenders", index=False)
    print(f"Excel export opgeslagen: {excel_path}")

    # Print samenvatting naar console
    print("\n" + report)

    if ai_analysis:
        print("\n" + "=" * 70)
        print("AI ANALYSE")
        print("=" * 70)
        print(ai_analysis)


def main():
    parser = argparse.ArgumentParser(description="Analyseer concurrenten-tenders in TenderNed dataset")
    parser.add_argument("--ai", action="store_true", help="Voer ook AI analyse uit (vereist ANTHROPIC_API_KEY)")
    parser.add_argument("--dataset", type=str, help="Pad naar dataset (optioneel, anders automatisch zoeken)")
    args = parser.parse_args()

    # Dataset vinden
    if args.dataset:
        dataset_path = Path(args.dataset)
    else:
        dataset_path = find_dataset()

    if not dataset_path or not dataset_path.exists():
        print("FOUT: Geen TenderNed dataset gevonden.")
        print(f"Verwacht patroon: {LOCAL_DATASET_PATTERN}")
        print(f"Zocht in: {PROJECT_ROOT}")
        print("Gebruik --dataset /pad/naar/bestand.xlsx om het pad op te geven.")
        sys.exit(1)

    # Dataset laden
    df = load_dataset(dataset_path)
    if df is None:
        sys.exit(1)

    # Concurrenten-tenders extraheren
    competitor_df = extract_competitor_tenders(df)
    if competitor_df.empty:
        print("Geen tenders gevonden van kernconcurrenten. Controleer de 'winning_company' kolom.")
        sys.exit(1)

    # Patronen analyseren
    print("\nPatronen analyseren...")
    analysis = analyze_patterns(competitor_df)

    # Rapport opmaken
    report = format_analysis_report(competitor_df, analysis)

    # AI analyse (optioneel)
    ai_analysis = ""
    if args.ai:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            print("WAARSCHUWING: ANTHROPIC_API_KEY niet gevonden. Sla AI analyse over.")
        else:
            ai_analysis = run_ai_analysis(competitor_df, api_key)

    # Opslaan
    save_outputs(competitor_df, analysis, report, ai_analysis)

    print(f"\nKlaar! Resultaten staan in: {OUTPUT_DIR}")
    print("\nVolgende stap: voeg de relevante bevindingen toe aan SKILLSTOWN_CONTEXT_DOCUMENT.md")


if __name__ == "__main__":
    main()
