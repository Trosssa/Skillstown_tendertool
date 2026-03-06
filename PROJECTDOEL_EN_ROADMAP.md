# SkillsTown TenderNed Analyzer - Projectdoel & Roadmap

> Dit document beschrijft het doel, de context en het plan van aanpak voor de tool.

---

## 1. Hoofddoel

**Een data-analyse tool die TenderNed aanbestedingsdata omzet naar bruikbare inzichten voor SkillsTown sales.**

### Wat doet de tool?
- Filtert relevante aanbestedingen (LMS, e-learning, trainingen) uit grote TenderNed datasets
- Groepeert resultaten per organisatie: wie schreef eerder relevante tenders uit?
- Toont concurrentie-informatie: welke partijen wonnen eerdere opdrachten?
- Rangschikt op AI-relevantiescore (primair), keyword score, en publicatiedatum
- Schat optioneel wanneer contracten kunnen verlopen (publicatiedatum + 3 jaar)

### Wat is het NIET?
- Geen CRM of bellijst-tool (daar gebruiken ze eigen systemen voor)
- Geen automatisch inschrijf-systeem
- Geen real-time monitoring

---

## 2. SkillsTown Profiel

### Producten
- **Inspire**: Online leerplatform (LMS/LXP), licentiemodel, 1000+ trainingen
- **Create**: Authoring tool voor eigen e-learnings
- **GetSpecialized**: Branchespecifieke trainingen (zorg, overheid, logistiek)

### Relevante sectoren
| Sector | Prioriteit | Reden |
|--------|------------|-------|
| Overheid (gemeenten, provincies, Rijk) | Hoogste | Partner Bestuursacademie Nederland |
| Zorg (ziekenhuizen, GGZ, thuiszorg) | Hoogste | BIG-nascholing, compliance |
| Onderwijs (MBO, HBO, universiteit, primair) | Hoogste | Docentprofessionalisering |
| Jeugdzorg, kinderopvang, retail, logistiek | Medium | Specialistische trainingen |

### 7 Directe concurrenten (CORE_COMPETITORS)
| Naam | Variaties in dataset |
|------|---------------------|
| Plusport | plusport, plus-port, plusport b.v., ... |
| GoodHabitz | goodhabitz, good habitz, goodhabitz b.v., ... |
| New Heroes | new heroes, newheroes, the new heroes, ... |
| StudyTube | studytube, study tube, studytube b.v., ... |
| Courseware | courseware, course ware, courseware b.v., ... |
| Online Academie | online academie, onlineacademie, online-academie, ... |
| Uplearning | uplearning, up learning, up-learning, ... |

Tenders gewonnen door deze partijen = **score override 100** (sterkste lead).

---

## 3. Kernlogica & Scoring

### Stap 1: Data laden
- Bestand: `Dataset_Tenderned*.xlsx` (lokaal, ~66MB, halfjaarlijks vernieuwd)
- 138,075 rijen, 112 kolommen; 45.8% heeft winning company ingevuld

### Stap 2: Pre-filtering
- **Keywords** (TERM_WEIGHTS in config.py): LMS=5, LXP=5, e-learning=4, leerplatform=4, blended learning=3, SCORM=3, webinar=2, management training=1, etc.
- **CPV-codes**: 18 codes (software, e-learning, opleidingen, IT-diensten)
- **Negatieve keywords**: vacatures, klassikale trainingen uitsluiten
- **Kernconcurrenten**: altijd door filter, ook zonder keyword match

### Stap 3: Keyword Score (0-100)
```python
calculate_keyword_score(title, description, winning_company, term_weights)
```
- Kernconcurrent als winnaar → score = 100 (override)
- Anders: gewogen frequentie-telling, genormaliseerd (cap = 60 raw punten → 100)

### Stap 4: AI Score (0-100) — primaire ranking
- Model: `claude-haiku-4-5-20251001` (~$0.10 per 1000 tenders)
- Context: `SKILLSTOWN_CONTEXT_DOCUMENT.md` + vaste scoringsgids
- Pre-filter: skip kernconcurrenten (al 100), skip >5 jaar oud, skip te kort
- Persistente cache: `cache/ai_scores.json` (MD5-hash)
- Velden in prompt: title, description, organization, CPV, winning_company, keyword_score, lot_description

### Stap 5: Datum filter (achtergrond)
- Brede slider: -1 tot +5 jaar verwachte herpublicatie
- Standaard AAN, maar niet leidend — alleen om extreem oude tenders weg te filteren
- Aanname: publicatiedatum + 3 jaar = geschatte herpublicatie

### Sorteervolgorde in UI
```
ai_score → keyword_score → publication_date
```

---

## 4. Huidige Status (Fase 6 voltooid — 2026-02-23)

### Wat werkt
- [x] Data laden uit TenderNed Excel (111+ kolommen mapping)
- [x] AUTO-LOAD lokale dataset via find_local_dataset()
- [x] Filteren op keywords (TERM_WEIGHTS, 40+) en CPV-codes (18)
- [x] Negatieve keywords filter (vacatures eruit)
- [x] Gewogen keyword-scoring (calculate_keyword_score)
- [x] Kernconcurrenten detectie → score override 100
- [x] Concurrentie detectie (7 kern + 30+ overige)
- [x] AI relevantie scoring (Claude Haiku, primaire ranking)
- [x] Organisatie-overzicht gesorteerd op AI → keyword → datum
- [x] Tijdlijn visualisatie (tenders per jaar + geschatte herpublicaties)
- [x] Seizoenspatroon detectie per organisatie
- [x] Export naar Excel
- [x] Zoekfunctie op organisaties en tenders
- [x] SkillsTown huisstijl
- [x] Datum als brede filter (slider -1 tot +5 jaar)
- [x] 93 unit tests
- [x] scripts/analyze_competitor_tenders.py

### Nog te doen
- [ ] ANTHROPIC_API_KEY instellen
- [ ] analyze_competitor_tenders.py --ai draaien
- [ ] SKILLSTOWN_CONTEXT_DOCUMENT.md aanvullen met analyse-output

---

## 5. Ontwikkelgeschiedenis

| Fase | Beschrijving | Status |
|------|-------------|--------|
| Fase 1 | Referentiedatum fix (publicatiedatum ipv gunningsdatum) | Voltooid |
| Fase 2 | Organisatie-view (groepering per organisatie) | Voltooid |
| Fase 3 | Seizoenslogica (kwartaal-voorspellingen) | Voltooid |
| Fase 4 | SkillsTown huisstijl | Voltooid |
| Fase 5 | Refactor naar data-analyse tool (weg van CRM/bellijst) | Voltooid |
| **Fase 6** | **Kernconcurrenten, gewogen scoring, AI primaire ranking, datum filter** | **Voltooid** |
| Fase 7 | Web scraping top 50 tenders (uitgesteld) | Gepland |

### Fase 6 wijzigingen (2026-02-23)
Aanleiding: sales meeting feedback — publicatiedatum-voorspelling is te onzeker als primair criterium.

**config.py:**
- CORE_COMPETITORS dict: 7 bedrijven met naamvariaties
- TERM_WEIGHTS: gewogen keyword-scoring (LMS=5 t/m mgmt=1)
- Nieuwe CPV-codes: 72260000-5, 72000000-5, 80520000-5 (gevonden in concurrent-tenders)
- Nieuwe termen: leeromgeving (4), digitale leeromgeving (4)

**filters.py:**
- is_core_competitor_win(): controleert winnaar tegen CORE_COMPETITORS
- calculate_keyword_score(): gewogen optelling, genormaliseerd, core competitor override
- filter_relevant_tenders(): core competitors altijd door filter
- add_match_details(): voegt keyword_score toe per tender

**ai_scorer.py:**
- should_analyze_with_ai(): skip kernconcurrenten (al 100), datum-check via publication_date
- get_skillstown_context(): structurele markdown met scoringsgids, producten, sectoren, concurrenten
- create_scoring_prompt(): winning_company, keyword_score, lot_description toegevoegd
- Model: claude-haiku-4-5-20251001

**app.py:**
- find_local_dataset() + load_local_dataset() voor automatisch laden
- Datum filter slider (-1 tot +5 jaar)
- Sort: ai_score → keyword_score → publication_date
- Kernconcurrenten apart in concurrentie-tab

**Nieuw:**
- SKILLSTOWN_CONTEXT_DOCUMENT.md (van CEO mail Joris)
- scripts/analyze_competitor_tenders.py
- cache/ map voor persistente AI scores

---

## 6. UI Layout

```
┌─ Sidebar ───────────────────────────┐
│ Data: Auto-load / Upload fallback   │
│ Filters: keywords, CPV, vacatures   │
│ Datum filter: slider -1 tot +5 jaar │
│ ▶ AI Relevantie Scoring             │
└─────────────────────────────────────┘

┌─ Main Content ──────────────────────┐
│ SkillsTown TenderNed Analyzer       │
│                                     │
│ [Metrics: Totaal | Relevant | Orgs] │
│                                     │
│ ┌─ TABS ──────────────────────────┐ │
│ │ Organisaties | Tenders |        │ │
│ │ Concurrentie | Tijdlijn |       │ │
│ │ Data Info                       │ │
│ └─────────────────────────────────┘ │
│                                     │
│ Organisaties tab:                   │
│ - Gesorteerd: AI score → keyword    │
│ - Tabel per organisatie             │
│ - Klikbare expanders met details    │
│ - Export naar Excel                 │
└─────────────────────────────────────┘
```

---

## 7. Bestandsoverzicht

| Bestand | Functie |
|---------|---------|
| `app.py` | Streamlit UI met 5 tabs, auto-load dataset, datum filter |
| `src/config.py` | TERM_WEIGHTS, CPV-codes, CORE_COMPETITORS, AI_CONFIG |
| `src/data_loader.py` | TenderNed Excel laden (string path + UploadedFile) |
| `src/filters.py` | Filter logica, calculate_keyword_score, is_core_competitor_win |
| `src/predictor.py` | Herpublicatie-schattingen, seizoenslogica |
| `src/org_analyzer.py` | Organisatie-aggregatie, relevantiescore, export |
| `src/ai_scorer.py` | Claude Haiku scoring, context document, persistente cache |
| `scripts/analyze_competitor_tenders.py` | Analyse van kernconcurrenten-tenders |
| `SKILLSTOWN_CONTEXT_DOCUMENT.md` | AI scoring context (CEO mail Joris) |
| `cache/ai_scores.json` | Persistente AI score cache |
| `tests/test_all.py` | 93 tests voor alle modules |

---

## 8. Snel Starten

```bash
pip install -r requirements.txt
streamlit run app.py
python -m pytest tests/test_all.py -v

# Concurrenten-analyse (vereist API key voor --ai):
python scripts/analyze_competitor_tenders.py
python scripts/analyze_competitor_tenders.py --ai
```

**AI scoring activeren:**
1. Stel `ANTHROPIC_API_KEY` in als environment variable
2. In de app: sidebar → "AI Relevantie Scoring" → aanvinken
3. Of draai eerst het analyze script om te testen

---

## 9. Data Bron

**TenderNed Datadump**
- URL: https://www.tenderned.nl/cms/nl/aanbesteden-in-cijfers/datasets-aanbestedingen
- Update frequentie: Elk half jaar
- Formaat: Excel (.xlsx)
- Inhoud: Alle aanbestedingen vanaf 2016
- Huidig bestand: Dataset_Tenderned-2016-01-01 tm 2025-12-31_Leeswijzer.xlsx

---

## 10. Changelog

| Datum | Wijziging |
|-------|-----------|
| 2026-02-03 | Initiële versie tool |
| 2026-02-03 | Negatieve keywords filter, concurrentie analyse |
| 2026-02-07 | Uitgebreid SkillsTown profiel onderzoek |
| 2026-02-07 | Zoektermen uitgebreid (18 → 40+), AI scoring |
| 2026-02-07 | Fase 1-4 voltooid (referentiedatum, organisatie-view, seizoenslogica, huisstijl) |
| 2026-02-11 | **Fase 5:** Refactor naar data-analyse tool (weg van CRM/bellijst concept) |
| 2026-02-23 | **Fase 6:** Kernconcurrenten, gewogen scoring, AI primaire ranking, datum filter, auto-load dataset |

---

*Laatst bijgewerkt: 2026-02-23*
