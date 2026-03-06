# SkillsTown TenderNed Analyzer

Data-analyse tool die TenderNed aanbestedingsdata omzet naar bruikbare verkoopinzichten.

## Wat doet de tool?

- Welke organisaties schreven eerder relevante tenders uit (LMS, e-learning, leerplatform)?
- Hoe lang geleden was dat — en wanneer verwachten we een nieuwe uitvraag?
- Wie was de vorige leverancier (concurrent)?
- Hoe groot was het contract?

Tenders worden gerangschikt op AI-relevantiescore (Claude Haiku), zodat de meest kansrijke organisaties bovenaan staan.

## De app gebruiken

1. Ga naar de app-URL (zie Slack/intranet)
2. Upload de TenderNed dataset (.xlsx bestand van de gedeelde schijf)
3. De app filtert automatisch op relevante tenders
4. Optioneel: schakel AI scoring in voor diepere analyse

### Tabs

| Tab | Inhoud |
|-----|--------|
| Organisaties | Analyse per organisatie, gesorteerd op kans |
| Tenders | Alle relevante tenders |
| Concurrentie | Tenders gewonnen door directe concurrenten |
| Tijdlijn | Tenders per jaar + verwachte herpublicaties |
| Data Info | Debug info over de geladen dataset |

## Dataset

Gebruik het bestand: `Dataset_Tenderned-2016-01-01 tm 2025-12-31_Leeswijzer.xlsx`

Te vinden op: _(vul hier de locatie van de gedeelde schijf in)_

## Lokaal draaien (voor ontwikkelaars)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Voor AI scoring: maak `.streamlit/secrets.toml` aan op basis van `.streamlit/secrets.toml.example`.

## Tests

```bash
python -m pytest tests/test_all.py -v
```
