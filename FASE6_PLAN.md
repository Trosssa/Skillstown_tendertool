# Fase 6 Plan: Betere Concurrentie-intel + AI Relevantie Scoring
> Opgesteld: 2026-02-23 | Gebaseerd op sales meeting feedback

---

## Achtergrond & Aanleiding

Sales meeting feedback (2026-02-23):
- Eerste versie goed ontvangen
- Publicatiedatum-voorspelling te veel "natte vinger werk" → deprioriteer
- **Concurrentie-matching is de meest waardevolle feature** — als een tender gewonnen is door een directe concurrent, is dat een heel sterk signaal
- Betere filtering gewenst: relevantie is nu nog te breed
- Gewenst: AI die context van omschrijvingen leest en relevantie bepaalt
- Idee: leer van concurrenten-tenders als trainingsdata voor AI context

---

## Prioriteitenlijst (volgorde van implementatie)

```
1. Concurrenten opschonen en uitbreiden met variaties     ← DIRECT DOEN
2. Concurrenten-tenders als input voor AI context         ← DIRECT DOEN
3. Betere keyword-scoring (frequentie = meer punten)      ← DIRECT DOEN
4. CEO mail verwerken in AI context document              ← WACHT OP INPUT
5. AI relevantie scoring als primaire rangschikking       ← NA 1-4
6. Datum als brede achtergrondfilter (1-5 jaar range)     ← NA 5
```

---

## TO-DO 1: Concurrenten opschonen

### Wat te doen
De huidige COMPETITORS lijst in `config.py` is zeer breed (authoring tools, LMS systemen, internationale platforms). Vervangen door alleen **directe Nederlandse concurrenten** die ook echt tenders winnen.

### Nieuwe kernconcurrenten (opgegeven door sales):
| Naam in config | Variaties toe te voegen |
|----------------|------------------------|
| `plusport` | `plus-port`, `plusport b.v.`, `plusport bv` |
| `goodhabitz` | `good habitz`, `goodhabitz b.v.`, `goodhabitz bv` |
| `new heroes` | `newheroes`, `the new heroes`, `new heroes b.v.` |
| `studytube` | `study tube`, `studytube b.v.`, `studytube bv` |
| `courseware` | `course ware`, `courseware b.v.` |
| `online academie` | `onlineacademie`, `online-academie`, `online academie b.v.` |
| `uplearning` | `up learning`, `up-learning`, `uplearning b.v.` |

### Scoring-aanpassing
Tenders die gewonnen zijn door één van deze directe concurrenten krijgen **maximale score (100)** — ongeacht andere criteria. Dit zijn de allersterkste leads.

### Wat eruit kan (te generiek / niet TenderNed-relevant)
- Authoring tools (Articulate, iSpring, Easygenerator etc.) — dit zijn tools, geen aanbieders die tenders winnen
- Internationale platforms die geen Nederlandse publieke tenders winnen (Coursera, Udemy, Pluralsight, Masterclass etc.)
- Detacheerders (Yacht, Brunel) — andere markt
- Uitgevers (Malmberg, Noordhoff) — andere markt
- Zorg-specifieke aanbieders die geen e-learning platform zijn

**Wel behouden (ook relevant voor overheids-tenders):**
- LinkedIn Learning, Skillsoft, Cornerstone, Docebo, Totara, Moodle, Brightspace — dit zijn echte LMS concurrenten die ook in NL tenders winnen

---

## TO-DO 2: Concurrenten-tenders als input voor AI context

### Concept
De tenders die onze directe concurrenten gewonnen hebben bevatten de meest relevante omschrijvingen — want dat zijn exact de opdrachten die wij ook willen winnen. Door deze te analyseren kunnen we:
1. Betere zoektermen genereren
2. Betere CPV-codes identificeren
3. De AI een veel rijker referentiekader geven

### Implementatie

#### Stap A: Concurrenten-tenders extraheren (nieuw script of tab)
Een apart script/functie `analyze_competitor_tenders.py` dat:
- Alle tenders filtert waar een van de 7 kernconcurrenten als winnaar staat
- De omschrijvingen, titels en CPV-codes exporteert naar een JSON bestand
- Output: `competitor_tenders_analysis.json`

#### Stap B: AI analyse van concurrenten-tenders
Een éénmalig script dat de concurrenten-tenders door Claude stuurt met de vraag:
- "Welke trefwoorden en CPV-codes komen het meest voor?"
- "Wat zijn typische kenmerken van deze aanbestedingen?"
- "Welke sectoren zijn vertegenwoordigd?"
Output: `SKILLSTOWN_CONTEXT_DOCUMENT.md` — een document dat beschrijft wat relevant is

#### Stap C: Context document integreren in AI scorer
De `get_skillstown_context()` functie in `ai_scorer.py` laadt het gegenereerde context document als aanvullende input voor de prompt.

### Benodigde input (ONTBREEKT NOG)
- **De TenderNed dataset moet beschikbaar zijn** om concurrenten-tenders te extraheren
- We hebben de dataset zelf nodig, niet alleen de gefilterde resultaten
- Vraag: is er een vaste dataset beschikbaar die we kunnen gebruiken als "trainingsdata"?

---

## TO-DO 3: Betere keyword-scoring

### Huidig probleem
Nu: tender matcht op 1 woord → komt door filter → krijgt evenveel gewicht als tender die op 10 woorden matcht

### Gewenste aanpak: gewogen scoring

```python
# Pseudo-code nieuwe scoring logica
score = 0

# Basis: aantal matches (frequentie)
for term in search_terms:
    count = text.lower().count(term.lower())
    score += count * TERM_WEIGHTS.get(term, 1)

# Bonus: directe concurrent als winnaar → maximale score
if winner in CORE_COMPETITORS:
    score = MAX_SCORE  # override alles

# Bonus: CPV match
if cpv_match:
    score += CPV_BONUS

# Bonus: meerdere matches (diversiteit)
if unique_matches >= 3:
    score += DIVERSITY_BONUS
```

### Gewichten per categorie
| Categorie | Gewicht | Rationale |
|-----------|---------|-----------|
| Directe concurrent als winnaar | MAX (100) | Sterkste indicator |
| LMS/LXP/e-learning platform | 5 | Kern product |
| Authoring tool (Create) | 4 | Kern product |
| CPV match (e-learning) | 3 | Goede indicator |
| Content/bibliotheek termen | 2 | Relevant |
| Generieke trainingsbegrippen | 1 | Zwakke indicator |

---

## TO-DO 4: CEO Mail verwerken in context ✅ ONTVANGEN

### Context
Mail van Joris (CEO) ontvangen op 2026-02-23. Bevat:
- Zoektermen: LMS, LXP, e-learning, leerplatform, opleidingsbroker, etc.
- CPV-codes per categorie (LMS software, e-learning content, trainingen)
- Werkwijze: 4 maanden voor verwachte publicatiedatum contact opnemen
- Kernlogica: publicatiedatum + 3 jaar = verwachte nieuwe uitvraag

### Verwerkt in
`SKILLSTOWN_CONTEXT_DOCUMENT.md` — dit is het context document voor de AI scorer.
Status: DRAFT — mist nog de concurrenten-tenders analyse sectie.

---

## TO-DO 5: AI als primaire relevantie-rangschikking

### Huidige situatie
- AI scoring bestaat al (`ai_scorer.py`) maar is optioneel en niet primair
- De pre-filtering is te grof (alles wat een keyword matcht gaat naar AI)
- AI context is beperkt (generiek SkillsTown profiel)

### Gewenste flow (na TO-DO 1-4)

```
Stap 1: GROVE FILTER (goedkoop, snel)
  → Alle tenders door basis keyword/CPV check
  → Alleen matches komen door
  → Directe concurrenten → direct maximale score, geen AI nodig

Stap 2: DATUM FILTER (breed, permissief)
  → Verwachte herpublicatie binnen 1-5 jaar
  → Of: publicatiedatum minder dan 4 jaar geleden (zodat ook recente tenders erin blijven)
  → Tenders ouder dan 5 jaar eruit

Stap 3: AI FIJNMAZIGE SCORING (per tender)
  → Claude Haiku voor kosten-efficiëntie (snel + goedkoop)
  → Context: SKILLSTOWN_CONTEXT_DOCUMENT.md (gegenereerd uit concurrenten-tenders + CEO mail)
  → Output: score 0-100 + uitleg + product match + sector

Stap 4: RANGSCHIKKING
  → Sorteer op AI score (hoog → laag)
  → Directe concurrent: altijd bovenaan (score 100)
  → Toon score en uitleg in UI
```

### Model keuze
- **Claude Haiku** voor individuele tender scoring (snel, goedkoop, goed genoeg)
- **Claude Sonnet** voor het éénmalig genereren van het context document

### Kosten inschatting
- Haiku: ~$0.25 per miljoen tokens
- Gemiddelde tender prompt: ~500 tokens → ~$0.0001 per tender
- 1000 tenders: ~$0.10 — verwaarloosbaar

---

## TO-DO 6: Datum als brede achtergrondfilter

### Aanpak (na TO-DO 5)
- Niet meer "verwachte publicatiedatum" als primair sorteerveld
- Wel als filter: toon alleen tenders waarbij verwachte herpublicatie **binnen 1-5 jaar** valt
- Standaard: filter aan, maar breed (1 jaar verleden tot 5 jaar toekomst)
- In UI: slider "Verwachte herpublicatie range" — niet leidend maar als achtergrondfilter
- Primaire sortering wordt: AI relevantie score

---

## TO-DO 7: TenderNed Web Scraping per tender (NIEUW — idee uit overleg 2026-02-23)

### Het idee
De TenderNed datadump bevat basisinfo per tender. Maar op TenderNed.nl zelf staat per tender
veel meer informatie — het volledige bestek, nota's van inlichtingen, gunningsbeslissing etc.
Idee: een agent laten scrapen voor extra info per tender.

### Haalbaarheid analyse

#### Wat TenderNed publiek beschikbaar heeft per tender:
- Aanbestedingspagina per tender via: `https://www.tenderned.nl/aankondigingen/overzicht/{tender_id}`
- Maar: veel documenten zijn alleen beschikbaar via login (Digipoort / overheid)
- De gunningsbeslissing (wie heeft gewonnen, voor welk bedrag) staat wel publiek
- Publicatiedatum, organisatie, omschrijving, CPV codes — staan al in de datadump

#### Technische mogelijkheden:
1. **Selenium/Playwright scraper** — kan publieke pagina's lezen, maar:
   - TenderNed heeft CAPTCHA beveiliging op sommige pagina's
   - Rate limiting (te snel scrapen = geblokkeerd)
   - Documentbestanden (PDF bestekken) zijn niet altijd publiek
   - Juridisch grijs gebied (ToS van TenderNed)

2. **TenderNed API** — TenderNed heeft een publieke API (Open Data):
   - `https://www.tenderned.nl/cms/nl/aanbesteden-in-cijfers/datasets-aanbestedingen`
   - De halfjaarlijkse datadump die we al gebruiken IS deze API
   - Geen extra endpoint voor volledig bestek per tender
   - Wel: gunningsbericht soms rijker dan datadump

3. **AI agent met web browsing** — Claude met tool use die per tender de pagina bezoekt:
   - Mogelijk voor publieke gunningsberichten
   - Langzaam (1 pagina per seconde = 1000 tenders = 16 minuten)
   - Kostbaar als je dit voor alle tenders doet
   - **Zinvol voor TOP tenders** (bijv. top 50 relevante, na AI scoring)

#### Aanbeveling:
**Fase 1 (nu):** Niet doen — de datadump bevat voldoende voor grove + fijne filtering
**Fase 2 (later):** Voor de TOP 50 meest relevante tenders (na AI scoring) een agent
  laten scrapen voor extra context — bijv. het volledige gunningsbericht
  Dit geeft: exacte contractwaarde, exacte winnaar, soms contractduur

#### Risico's en beperkingen:
- TenderNed ToS — scraping is formeel niet toegestaan (gebruik officiële API)
- Documenten (bestekken) zijn achter login
- Data inconsistent — niet alle tenders hebben een publiek gunningsbericht

#### Conclusie:
Interessant idee, maar complex en risicovol voor grote schaal. Beter toepassen op
een kleine set (top relevante tenders na AI filtering). Documenteer als Fase 7 idee.

---

## Dataset situatie ✅ Opgelost (2026-02-23)

**Bestand:** `Dataset_Tenderned-2016-01-01 tm 2025-12-31_Leeswijzer.xlsx` (66MB)
**Locatie:** Lokaal op schijf in `Skillstown/` — staat in `.gitignore` (te groot voor git)
**Inhoud:** Vermoedelijk één Excel met meerdere sheets: data + leeswijzer

**Implicaties voor implementatie:**
1. Het concurrenten-analyse script kan dit bestand direct inladen via lokaal pad
2. De app kan bij opstarten kijken of dit bestand aanwezig is → automatisch laden ipv upload
3. Toekomstige updates: nieuwe dataset in dezelfde map plaatsen → app pikt het op

**TO-DO (toegevoegd):** App aanpassen zodat hij bij aanwezigheid van het lokale bestand
dit automatisch laadt — geen upload nodig. Bij afwezigheid: toon upload widget als fallback.

---

## Vragen / Ontbrekende Context

### OPGELOST:
1. ~~**CEO Mail**~~ ✅ Ontvangen (2026-02-23)
2. ~~**Dataset beschikbaarheid**~~ ✅ Bevestigd — lokaal aanwezig op schijf

### NOG HANDIG MAAR NIET BLOKKEREND:
3. Zijn er specifieke tenders die sales als "perfect match" beschouwt? Als positieve voorbeelden voor AI scorer.
4. Zijn er tenders die de tool vond maar die sales als "irrelevant" beschouwt? Als negatieve voorbeelden.
5. Plusport: hoe actief zijn ze op TenderNed? (Beïnvloedt gewichtstoewijzing)

---

## Technische impact per bestand

| Bestand | Wijzigingen Fase 6 |
|---------|-------------------|
| `src/config.py` | COMPETITORS lijst opschonen, kernconcurrenten apart, term weights toevoegen |
| `src/filters.py` | Gewogen scoring, concurrenten-bonus logica |
| `src/ai_scorer.py` | Context document laden, betere prompt, Haiku als default |
| `src/predictor.py` | Datum filter verbreden (1-5 jaar range) |
| `app.py` | AI score als primair sorteerveld, datum als filter (niet sortering) |
| `analyze_competitor_tenders.py` | NIEUW: éénmalig analyse script |
| `SKILLSTOWN_CONTEXT_DOCUMENT.md` | NIEUW: gegenereerd context document voor AI |
| `tests/test_all.py` | Tests bijwerken voor nieuwe scoring logica |

---

## Technische impact per bestand (uitgebreid)

| Bestand | Wijzigingen Fase 6 |
|---------|-------------------|
| `app.py` (TO-DO 0) | Lokale dataset automatisch laden bij aanwezigheid, upload als fallback |
| `src/config.py` | COMPETITORS opsplitsen: CORE_COMPETITORS (7) + SECONDARY_COMPETITORS, TERM_WEIGHTS toevoegen |
| `src/filters.py` | Gewogen scoring, core concurrent = score 100 override |
| `src/ai_scorer.py` | SKILLSTOWN_CONTEXT_DOCUMENT.md laden als context, Haiku als default, betere prompt |
| `src/predictor.py` | Datum filter verbreden (1-5 jaar range, niet als sortering) |
| `app.py` | AI score primair sorteerveld, datum als filter-slider in sidebar |
| `scripts/analyze_competitor_tenders.py` | NIEUW: éénmalig analyse script |
| `SKILLSTOWN_CONTEXT_DOCUMENT.md` | NIEUW: context document ✅ DRAFT aangemaakt |
| `tests/test_all.py` | Tests bijwerken voor nieuwe scoring logica |

---

## Volgorde van implementatie

```
VOLTOOID (2026-02-23):
  [x] TO-DO 0: App laadt lokale dataset automatisch (app.py)
  [x] TO-DO 1: CORE_COMPETITORS (7) + SECONDARY_COMPETITORS in config.py
  [x] TO-DO 2: scripts/analyze_competitor_tenders.py gebouwd
  [x] TO-DO 3: TERM_WEIGHTS + calculate_keyword_score() in filters.py
  [x] TO-DO 4: SKILLSTOWN_CONTEXT_DOCUMENT.md DRAFT klaar (CEO mail verwerkt)
  [x] TO-DO 5: AI als primaire ranking (Haiku, context document, sort op score)
  [x] TO-DO 6: Datum als brede achtergrondfilter (1-5 jaar range slider in sidebar)
  [x] Tests: 92/92 geslaagd

WACHT OP UITVOERING:
  [ ] TO-DO 2 UITVOEREN: python scripts/analyze_competitor_tenders.py --ai
      → Vereist: ANTHROPIC_API_KEY in omgeving
      → Output: scripts/output/competitor_analysis.txt + competitor_tenders.json
      → Daarna: bevindingen verwerken in SKILLSTOWN_CONTEXT_DOCUMENT.md

Fase 7 (later):
  [ ] TO-DO 7: Web scraping top-tenders → klein script, alleen top 50 na AI scoring
```

---

*Opgesteld: 2026-02-23*
*Update 2026-02-23: CEO mail ontvangen en verwerkt, TO-DO 7 (web scraping) toegevoegd*
