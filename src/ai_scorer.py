"""
AI-powered relevance scoring for TenderNed tenders.
Uses Claude API to assess how relevant a tender is for SkillsTown.

Slim compute gebruik:
- Pre-filtering: alleen tenders die door basis filters komen
- Datum filter: alleen toekomstige/recente tenders (niet oud)
- Minimum tekstlengte: te korte omschrijvingen overslaan
- Caching: voorkom dubbele API calls
"""

import hashlib
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import pandas as pd

from .config import AI_CONFIG, COMPETITORS, CORE_COMPETITORS, NEGATIVE_KEYWORDS, SECTORS

# Try to import anthropic, gracefully handle if not installed
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


def is_anthropic_available() -> bool:
    """Check if the anthropic library is installed."""
    return ANTHROPIC_AVAILABLE


def create_tender_hash(tender: dict) -> str:
    """Create a unique hash for a tender to use as cache key."""
    key_fields = ["title", "description", "organization"]
    content = "|".join(str(tender.get(f, "")) for f in key_fields)
    return hashlib.md5(content.encode()).hexdigest()


# --- Persistent file-based cache ---

CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_FILE = CACHE_DIR / "ai_scores.json"


def _load_persistent_cache() -> dict:
    """Load cached AI scores from local JSON file."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def apply_cached_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Laad gecachede AI scores uit cache/ai_scores.json en pas ze toe op het DataFrame.
    Werkt zonder API key — toont eerder berekende scores direct bij opstarten.
    """
    cache = _load_persistent_cache()
    if not cache:
        return df

    result_df = df.copy()
    if "ai_score" not in result_df.columns:
        result_df["ai_score"] = None
        result_df["ai_explanation"] = None
        result_df["ai_product"] = None
        result_df["ai_sector"] = None
        result_df["ai_confidence"] = None
        result_df["ai_analyzed"] = False

    for idx, row in result_df.iterrows():
        tender = row.to_dict()
        tender_hash = create_tender_hash(tender)
        if tender_hash in cache:
            cached = cache[tender_hash]
            if cached.get("error"):
                continue  # Sla error-entries over, laat ze opnieuw worden geanalyseerd
            result_df.at[idx, "ai_score"] = cached.get("relevance_score")
            result_df.at[idx, "ai_explanation"] = cached.get("explanation")
            result_df.at[idx, "ai_product"] = cached.get("best_product")
            result_df.at[idx, "ai_sector"] = cached.get("sector_match")
            result_df.at[idx, "ai_confidence"] = cached.get("confidence")
            result_df.at[idx, "ai_analyzed"] = True

    return result_df


def _save_persistent_cache(cache: dict) -> None:
    """Save AI scores cache to local JSON file."""
    CACHE_DIR.mkdir(exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def should_analyze_with_ai(tender: dict, today: Optional[datetime] = None) -> tuple[bool, str]:
    """
    Pre-filter: bepaal of deze tender AI analyse nodig heeft.

    Returns:
        tuple: (should_analyze: bool, reason: str)
    """
    if today is None:
        today = datetime.now()

    # Check 1: Core competitor als winnaar → score is al 100, geen AI nodig
    # Voorkomt verspilling van API calls op tenders die we al maximaal scoren.
    keyword_score = tender.get("keyword_score")
    if keyword_score is not None and not pd.isna(keyword_score) and int(keyword_score) == 100:
        return False, "Kernconcurrent (score al 100)"

    match_type = str(tender.get("match_type", "")).lower()
    if "kernconcurrent" in match_type:
        return False, "Kernconcurrent (score al 100)"

    # Check 2: Moet door keyword/CPV filter zijn gekomen
    if AI_CONFIG.get("require_keyword_match", True):
        matched_terms = tender.get("matched_terms", "")
        matched_cpv = tender.get("matched_cpv", "")
        if not matched_terms and not matched_cpv:
            return False, "Geen keyword/CPV match"

    # Check 3: Niet te oud — check op publicatiedatum, niet op days_until_contact
    # days_until_contact is fragiel (NaN als predictor niet gelopen heeft)
    max_days_past = AI_CONFIG.get("max_days_in_past", 1825)
    pub_date = tender.get("publication_date")
    if pub_date is not None and not pd.isna(pub_date):
        try:
            pub_dt = pd.to_datetime(pub_date)
            days_old = (today - pub_dt).days
            if days_old > max_days_past:
                return False, f"Te oud ({days_old} dagen geleden, max {max_days_past})"
        except (TypeError, ValueError):
            pass  # Als datum niet parseerbaar is, doorgaan

    # Check 4: Voldoende tekst voor analyse
    min_length = AI_CONFIG.get("min_description_length", 50)
    description = str(tender.get("description", "") or "")
    title = str(tender.get("title", "") or "")
    total_text = len(description) + len(title)

    if total_text < min_length:
        return False, f"Te weinig tekst ({total_text} < {min_length} karakters)"

    return True, "OK"


def _extract_context_sections(doc: str, section_headers: list[str]) -> str:
    """
    Extraheer specifieke secties uit een Markdown document op basis van ## headers.
    Geeft de gevonden secties samen terug als tekst.
    """
    if not doc:
        return ""

    lines = doc.split("\n")
    result_parts = []
    in_section = False
    current_section_lines = []

    for line in lines:
        # Nieuwe ## header
        if line.startswith("##"):
            # Sla huidige sectie op als die relevant was
            if in_section and current_section_lines:
                result_parts.append("\n".join(current_section_lines))
            current_section_lines = []
            in_section = any(header.lower() in line.lower() for header in section_headers)
            if in_section:
                current_section_lines.append(line)
        elif in_section:
            # Stop bij een nieuwe # header (hogere niveau)
            if line.startswith("# ") and not line.startswith("##"):
                in_section = False
            else:
                current_section_lines.append(line)

    # Laatste sectie opslaan
    if in_section and current_section_lines:
        result_parts.append("\n".join(current_section_lines))

    return "\n\n".join(result_parts)


def get_skillstown_context() -> str:
    """
    Bouw de volledige SkillsTown context op voor de AI scoring prompt.

    Combineert:
    1. Vaste kernbeschrijving (producten, concurrenten, niet-relevant)
    2. Relevante secties uit SKILLSTOWN_CONTEXT_DOCUMENT.md (als aanwezig)
    """
    core_names = list(CORE_COMPETITORS.keys())

    # Laad het context document
    context_path = Path(__file__).parent.parent / "SKILLSTOWN_CONTEXT_DOCUMENT.md"
    context_doc = ""
    if context_path.exists():
        try:
            with open(context_path, "r", encoding="utf-8") as f:
                context_doc = f.read()
        except IOError:
            pass

    # Extraheer de meest relevante secties uit het context document
    # (scoringskader, CPV-codes, wat wel/niet relevant is)
    useful_sections = _extract_context_sections(context_doc, [
        "Wat maakt een tender RELEVANT",
        "CPV-codes die sterk",
        "Zoektermen",
        "Wat NIET relevant is",
        "aanbestedingscyclus",
    ])

    context = f"""Je beoordeelt aanbestedingen voor SkillsTown, een Nederlandse aanbieder van online leeroplossingen.

## SkillsTown producten
- **Inspire**: Online leerplatform (LMS/LXP) — licentiemodel, 1000+ trainingen, sectoren: overheid, zorg, onderwijs
- **Create**: Authoring tool — organisaties maken eigen e-learning modules mee
- **GetSpecialized**: Branchespecifieke trainingen (zorg, overheid, logistiek)

## Sectoren (prioriteit voor SkillsTown)
- Overheid (gemeenten, provincies, rijksoverheid) — hoogste prioriteit
- Zorg (ziekenhuizen, GGZ, thuiszorg) — hoogste prioriteit
- Onderwijs (MBO, HBO, universiteit, primair onderwijs) — hoogste prioriteit
- Jeugdzorg, kinderopvang, retail, logistiek — medium prioriteit

## Directe concurrenten
Als een tender gewonnen is door een van onderstaande partijen, is dat een STERKE LEAD:
het contract loopt af en de organisatie gaat opnieuw aanbesteden.
Directe concurrenten: {', '.join(core_names)}
Overige concurrenten (ook relevant): LinkedIn Learning, Skillsoft, Cornerstone, Docebo, Totara, Moodle, Brightspace

## Scoringskader

**Score 80-100 — Zeer relevant:**
- Expliciete vraag naar LMS, LXP, e-learning platform, leeromgeving, leerplatform
- Vraag naar e-learning bibliotheek of contentlicenties (past bij Inspire)
- Vraag naar authoring tool of maatwerk e-learning ontwikkeling (past bij Create)
- Vorige winnaar is een directe concurrent (contract loopt af)
- Opleidingsbroker of opleidingsintermediair gevraagd

**Score 60-79 — Relevant:**
- Online leren / digitaal leren als kern van de opdracht
- Blended learning waarbij digitaal component duidelijk aanwezig is
- SCORM of LTI integratie gevraagd (technische integratie met platform)
- Combinatie van training + platform/systeem
- Overheid of zorg als aanbestedende organisatie met e-learning component

**Score 40-59 — Mogelijk relevant:**
- Trainingen en opleidingen met digitale component, maar platform niet expliciet
- E-learning content ontwikkeling zonder platformvraag
- Sector matcht (overheid/zorg/onderwijs) maar digitaal onduidelijk

**Score 20-39 — Beperkt relevant:**
- Generieke opleidingsvraag zonder duidelijk digitaal platform component
- Trainingscatalogus of opleidingsaanbod, maar waarschijnlijk klassikaal

**Score 0-19 — Niet relevant:**
- Vacatures of personeelswerving (medewerker, FTE, sollicitatie, teamleider)
- Puur klassikale / fysieke trainingen zonder digitale component
- Inhuur van externe trainers of consultants (geen platform gezocht)
- Puur technisch/vaktechnisch onderwijs (rijschool, BHV, VCA, veiligheid op locatie)
- Bouw, infra, catering, transport — geen link met leeroplossingen"""

    # Voeg secties uit het context document toe als die beschikbaar en informatief zijn
    if useful_sections and len(useful_sections) > 200:
        context += f"\n\n## Aanvullende context (SkillsTown analyse)\n{useful_sections[:2000]}"

    return context


def create_scoring_prompt(tender: dict) -> str:
    """Create the prompt for AI scoring."""
    context = get_skillstown_context()

    title = tender.get("title", "Geen titel")
    description = tender.get("description", "Geen omschrijving")
    lot_description = tender.get("lot_description", "")
    organization = tender.get("organization", "Onbekend")
    cpv_codes = tender.get("cpv_codes", "")
    matched_terms = tender.get("matched_terms", "")
    winning_company = tender.get("winning_company", "")
    keyword_score = tender.get("keyword_score", "")

    # Combineer omschrijving en perceelbeschrijving
    full_description = str(description) if pd.notna(description) else ""
    if lot_description and pd.notna(lot_description) and str(lot_description).strip():
        full_description += f"\n\n[Perceel] {lot_description}"
    full_description = full_description[:2500]

    # Voorgaande winnaar-toelichting
    winner_line = ""
    if winning_company and str(winning_company).strip() and str(winning_company) != "nan":
        winner_line = f"\n- Vorige winnaar: {winning_company}"

    return f"""{context}

---

Beoordeel onderstaande aanbesteding voor SkillsTown.

## Tender informatie
- Titel: {title}
- Organisatie: {organization}
- CPV codes: {cpv_codes}
- Gematchte zoektermen: {matched_terms}{winner_line}
- Gewogen keyword score (0-100): {keyword_score if keyword_score != "" else "onbekend"}

## Omschrijving
{full_description if full_description.strip() else "Geen omschrijving beschikbaar."}

---

Geef je beoordeling in dit exacte JSON formaat (geen andere tekst):
{{
    "relevance_score": <integer 0-100>,
    "explanation": "<max 60 woorden: waarom deze score, wat mist of past goed>",
    "best_product": "<Inspire|Create|GetSpecialized|Geen>",
    "sector_match": "<Overheid|Zorg|Onderwijs|Jeugdzorg|Kinderopvang|Retail|Logistiek|Overig|Geen>",
    "confidence": "<Hoog|Medium|Laag>"
}}

Richtlijn bij twijfel: laat de inhoud van de omschrijving leidend zijn, niet alleen de titel."""


def parse_ai_response(response_text: str) -> dict:
    """Parse the AI response JSON."""
    try:
        # Try to extract JSON from response
        text = response_text.strip()

        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        result = json.loads(text.strip())

        # Validate required fields
        required_fields = ["relevance_score", "explanation", "best_product", "sector_match", "confidence"]
        for field in required_fields:
            if field not in result:
                result[field] = None

        # Ensure score is in range
        score = result.get("relevance_score", 0)
        if isinstance(score, (int, float)):
            result["relevance_score"] = max(0, min(100, int(score)))
        else:
            result["relevance_score"] = 0

        return result

    except (json.JSONDecodeError, IndexError, KeyError) as e:
        return {
            "relevance_score": 0,
            "explanation": f"Parse error: {str(e)}",
            "best_product": None,
            "sector_match": None,
            "confidence": "Laag",
            "error": True
        }


def score_single_tender(
    tender: dict,
    api_key: str,
    model: str = "claude-haiku-4-5-20251001"
) -> dict:
    """
    Score a single tender using Claude API.

    Gebruikt prompt caching voor de vaste SkillsTown-context:
    - System message met cache_control → context wordt 1x gecached per sessie
    - Scheelt ~80% op input token kosten bij grote batches

    Args:
        tender: Dictionary with tender data
        api_key: Anthropic API key
        model: Model to use (default: claude-haiku for cost efficiency)

    Returns:
        Dictionary with scoring results
    """
    if not ANTHROPIC_AVAILABLE:
        return {
            "relevance_score": 0,
            "explanation": "Anthropic library niet geinstalleerd",
            "best_product": None,
            "sector_match": None,
            "confidence": "Laag",
            "error": True
        }

    try:
        client = anthropic.Anthropic(api_key=api_key)

        # Bouw tender-specifieke prompt (zonder de vaste context)
        title = tender.get("title", "Geen titel")
        description = tender.get("description", "Geen omschrijving")
        lot_description = tender.get("lot_description", "")
        organization = tender.get("organization", "Onbekend")
        cpv_codes = tender.get("cpv_codes", "")
        matched_terms = tender.get("matched_terms", "")
        winning_company = tender.get("winning_company", "")
        keyword_score = tender.get("keyword_score", "")

        full_description = str(description) if pd.notna(description) else ""
        if lot_description and pd.notna(lot_description) and str(lot_description).strip():
            full_description += f"\n\n[Perceel] {lot_description}"
        full_description = full_description[:2500]

        winner_line = ""
        if winning_company and str(winning_company).strip() and str(winning_company) != "nan":
            winner_line = f"\n- Vorige winnaar: {winning_company}"

        user_prompt = f"""Beoordeel onderstaande aanbesteding voor SkillsTown.

## Tender informatie
- Titel: {title}
- Organisatie: {organization}
- CPV codes: {cpv_codes}
- Gematchte zoektermen: {matched_terms}{winner_line}
- Gewogen keyword score (0-100): {keyword_score if keyword_score != "" else "onbekend"}

## Omschrijving
{full_description if full_description.strip() else "Geen omschrijving beschikbaar."}

---

Geef je beoordeling in dit exacte JSON formaat (geen andere tekst):
{{
    "relevance_score": <integer 0-100>,
    "explanation": "<max 60 woorden: waarom deze score, wat mist of past goed>",
    "best_product": "<Inspire|Create|GetSpecialized|Geen>",
    "sector_match": "<Overheid|Zorg|Onderwijs|Jeugdzorg|Kinderopvang|Retail|Logistiek|Overig|Geen>",
    "confidence": "<Hoog|Medium|Laag>"
}}

Richtlijn bij twijfel: laat de inhoud van de omschrijving leidend zijn, niet alleen de titel."""

        # Vaste context in system message met cache_control
        # → Anthropic cached dit na de 1e aanroep; volgende tenders betalen ~10% van deze tokens
        system_context = get_skillstown_context()

        message = client.messages.create(
            model=model,
            max_tokens=500,
            system=[
                {
                    "type": "text",
                    "text": system_context,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        response_text = message.content[0].text
        result = parse_ai_response(response_text)
        result["model_used"] = model
        result["error"] = False

        return result

    except anthropic.APIError as e:
        error_msg = str(e)
        return {
            "relevance_score": 0,
            "explanation": f"API error: {error_msg}",
            "best_product": None,
            "sector_match": None,
            "confidence": "Laag",
            "error": True,
            "error_type": "credits" if "credit balance" in error_msg else "api_error"
        }
    except Exception as e:
        return {
            "relevance_score": 0,
            "explanation": f"Error: {str(e)}",
            "best_product": None,
            "sector_match": None,
            "confidence": "Laag",
            "error": True,
            "error_type": "unknown"
        }


def score_tenders_batch(
    df: pd.DataFrame,
    api_key: str,
    cache: Optional[dict] = None,
    progress_callback: Optional[callable] = None,
    model: str = "claude-haiku-4-5-20251001"
) -> pd.DataFrame:
    """
    Score multiple tenders with AI, using pre-filtering and caching.

    Args:
        df: DataFrame with tender data (already filtered by keywords/CPV)
        api_key: Anthropic API key
        cache: Optional dict to cache results (key: tender_hash, value: result)
        progress_callback: Optional callback(current, total, tender_title) for progress updates
        model: Model to use

    Returns:
        DataFrame with added AI scoring columns
    """
    if cache is None:
        cache = {}

    # Merge persistent cache into session cache
    persistent_cache = _load_persistent_cache()
    for k, v in persistent_cache.items():
        if k not in cache:
            cache[k] = v

    result_df = df.copy()

    # Initialize new columns
    result_df["ai_score"] = None
    result_df["ai_explanation"] = None
    result_df["ai_product"] = None
    result_df["ai_sector"] = None
    result_df["ai_confidence"] = None
    result_df["ai_analyzed"] = False
    result_df["ai_skip_reason"] = None

    # Count how many need analysis
    to_analyze = []
    for idx, row in result_df.iterrows():
        tender = row.to_dict()
        should_analyze, reason = should_analyze_with_ai(tender)

        if should_analyze:
            tender_hash = create_tender_hash(tender)
            to_analyze.append((idx, tender, tender_hash))
        else:
            result_df.at[idx, "ai_skip_reason"] = reason

    total = len(to_analyze)

    # Process tenders
    for i, (idx, tender, tender_hash) in enumerate(to_analyze):
        # Check cache first — sla error-entries over zodat ze opnieuw worden geprobeerd
        if tender_hash in cache:
            cached_result = cache[tender_hash]
            if not cached_result.get("error"):
                result_df.at[idx, "ai_score"] = cached_result.get("relevance_score")
                result_df.at[idx, "ai_explanation"] = cached_result.get("explanation")
                result_df.at[idx, "ai_product"] = cached_result.get("best_product")
                result_df.at[idx, "ai_sector"] = cached_result.get("sector_match")
                result_df.at[idx, "ai_confidence"] = cached_result.get("confidence")
                result_df.at[idx, "ai_analyzed"] = True
                result_df.at[idx, "ai_skip_reason"] = "Cached"
                continue
            # Error-entry gevonden → verwijder uit cache en probeer opnieuw
            del cache[tender_hash]

        # Progress callback
        if progress_callback:
            progress_callback(i + 1, total, tender.get("title", ""))

        # Score with AI
        result = score_single_tender(tender, api_key, model)

        # Store in cache
        cache[tender_hash] = result

        # Store in DataFrame
        result_df.at[idx, "ai_score"] = result.get("relevance_score")
        result_df.at[idx, "ai_explanation"] = result.get("explanation")
        result_df.at[idx, "ai_product"] = result.get("best_product")
        result_df.at[idx, "ai_sector"] = result.get("sector_match")
        result_df.at[idx, "ai_confidence"] = result.get("confidence")
        result_df.at[idx, "ai_analyzed"] = True

        if result.get("error"):
            result_df.at[idx, "ai_skip_reason"] = "Error"

    # Save updated cache to disk
    _save_persistent_cache(cache)

    return result_df


def get_ai_summary(df: pd.DataFrame) -> dict:
    """Get summary statistics of AI scoring."""
    analyzed = df[df["ai_analyzed"] == True]

    if len(analyzed) == 0:
        return {
            "total_analyzed": 0,
            "avg_score": 0,
            "high_relevance": 0,
            "medium_relevance": 0,
            "low_relevance": 0,
        }

    scores = analyzed["ai_score"].dropna()

    return {
        "total_analyzed": len(analyzed),
        "total_skipped": len(df) - len(analyzed),
        "avg_score": round(scores.mean(), 1) if len(scores) > 0 else 0,
        "high_relevance": len(scores[scores >= 60]),
        "medium_relevance": len(scores[(scores >= 40) & (scores < 60)]),
        "low_relevance": len(scores[scores < 40]),
        "by_product": analyzed["ai_product"].value_counts().to_dict(),
        "by_sector": analyzed["ai_sector"].value_counts().to_dict(),
    }


def filter_by_ai_score(
    df: pd.DataFrame,
    min_score: int = 40
) -> pd.DataFrame:
    """Filter tenders by minimum AI relevance score."""
    threshold = AI_CONFIG.get("relevance_threshold", min_score)

    # Keep tenders that either:
    # 1. Have AI score >= threshold
    # 2. Were not analyzed (ai_score is None) - don't exclude these
    mask = (df["ai_score"].isna()) | (df["ai_score"] >= threshold)

    return df[mask].copy()
