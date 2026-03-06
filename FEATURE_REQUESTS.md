# Feature Requests - SkillsTown TenderNed Analyzer

> **Context:** Dit is een data-analyse tool, geen CRM. Elke feature moet bijdragen aan
> betere inzichten uit TenderNed data. Zie PROJECTDOEL_EN_ROADMAP.md voor het complete doel.

---

## Voltooid

| Feature | Datum | Beschrijving |
|---------|-------|-------------|
| Negatieve Keywords Filter | 2026-02-03 | Vacatures uitsluiten |
| Concurrentie Analyse | 2026-02-03 | Detectie van bekende concurrenten |
| Uitgebreide Config | 2026-02-07 | 40+ zoektermen, 50+ concurrenten |
| AI Relevantie Scoring | 2026-02-07 | Optionele Claude API scoring |
| Referentiedatum Fix | 2026-02-07 | Publicatiedatum ipv gunningsdatum |
| Organisatie-View | 2026-02-07 | Groepering per organisatie |
| Seizoenslogica | 2026-02-07 | Kwartaal-voorspellingen |
| SkillsTown Huisstijl | 2026-02-07 | Professionele UI |
| Data-analyse refactor | 2026-02-11 | Weg van CRM/bellijst, puur analyse |
| **Fase 6: Kernconcurrenten** | 2026-02-23 | 7 directe concurrenten, score override 100 |
| **Fase 6: Gewogen keyword-scoring** | 2026-02-23 | TERM_WEIGHTS (LMS=5 t/m mgmt=1), genormaliseerd |
| **Fase 6: Concurrenten-analyse script** | 2026-02-23 | scripts/analyze_competitor_tenders.py |
| **Fase 6: CEO mail verwerkt** | 2026-02-23 | SKILLSTOWN_CONTEXT_DOCUMENT.md aangemaakt |
| **Fase 6: AI als primaire ranking** | 2026-02-23 | ai_scorer.py herschreven, Haiku model |
| **Fase 6: Datum als brede filter** | 2026-02-23 | Slider -1 tot +5 jaar, standaard aan |
| **Fase 6: Auto-load lokale dataset** | 2026-02-23 | find_local_dataset() in app.py |

---

## Openstaand — Hoge prioriteit

- [ ] **ANTHROPIC_API_KEY instellen** en AI scoring activeren
  - Set in environment of .env bestand
  - Eerst draaien op: `python scripts/analyze_competitor_tenders.py --ai` (17 tenders, goedkoop)
  - Daarna: AI scoring in app inschakelen voor volledige gefilterde dataset

- [ ] **SKILLSTOWN_CONTEXT_DOCUMENT.md aanvullen** met resultaten analyze script
  - Na het draaien van `--ai` mode: output gebruiken om context doc te verrijken
  - Specifiek: welke CPV-codes en beschrijvingen kwamen voor in concurrenten-tenders?

---

## Ideeën voor later

### Analyse verbeteringen
- [ ] Fase 7: Web scraping van top 50 tenders na AI scoring (uitgesteld)
  Details: scripts/analyze_competitor_tenders.py is al gebouwd voor de output-structuur
- [ ] Sector-classificatie per organisatie (overheid/zorg/onderwijs)
- [ ] Historische trend: contractwaarde over tijd
- [ ] Vergelijking tussen periodes (bv. 2020-2022 vs 2023-2025)
- [ ] Positieve/negatieve voorbeeldtenders aanleveren door sales (voor AI fine-tuning)

### Data
- [ ] TenderNed API integratie (automatisch laden ipv handmatige upload)
- [ ] Meerdere datasets tegelijk laden en vergelijken

### Export
- [ ] Aangepaste export templates (kies welke kolommen)

---

*Laatst bijgewerkt: 2026-02-23*
