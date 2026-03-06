"""
Configuration for SkillsTown TenderNed Analyzer.
Contains search terms and CPV codes for identifying relevant tenders.

Laatste update: 2026-02-23
- Fase 6: CORE_COMPETITORS (7 directe concurrenten) apart gedefinieerd
- Fase 6: TERM_WEIGHTS toegevoegd voor gewogen keyword-scoring
- 2026-02-07: Uitgebreid met sectortermen, leervormen en thema's
"""

# ===============================================
# ZOEKTERMEN + GEWICHTEN
# ===============================================
# Gewicht bepaalt hoe zwaar een match meetelt in de relevantiescore.
# Gewichten zijn gebaseerd op hoe direct de term SkillsTown's kernproducten raakt.

TERM_WEIGHTS = {
    # === Gewicht 5: Kern producten — directe match ===
    "LMS":                          5,
    "Leermanagementsysteem":        5,
    "leermanagementsysteem":        5,
    "LXP":                          5,
    "learning experience platform": 5,
    "e-learning platform":          5,
    "online leerplatform":          5,
    "leerplatform":                 5,
    "E-learning bibliotheek":       5,
    "e-learning bibliotheek":       5,
    "auteurstool":                  5,
    "authoringtool":                5,
    "authoring tool":               5,
    "opleidingsbroker":             5,
    "opleidingsintermediair":       5,

    # === Gewicht 4: Sterk relevant ===
    "E-learning":                   4,
    "e-learning":                   4,
    "online learning":              4,
    "online leren":                 4,
    "digitaal leren":               4,
    "maatwerk e-learning":          4,
    "leercontent":                  4,
    "leerinhoud":                   4,
    "leeromgeving":                 4,  # gevonden in StudyTube-tenders (Digitale LeerOmgeving)
    "digitale leeromgeving":        4,
    "opleidingscatalogus":          4,
    "trainingscatalogus":           4,
    "leerportaal":                  4,
    "kennisportaal":                4,

    # === Gewicht 3: Relevant ===
    "blended learning":             3,
    "hybride leren":                3,
    "SCORM":                        3,
    "LTI koppeling":                3,
    "LTI integratie":               3,
    "digitale leermiddelen":        3,
    "leermateriaal":                3,
    "cursusmateriaal":              3,
    "trainingsmateriaal":           3,

    # === Gewicht 2: Contextueel relevant ===
    "webinar":                      2,
    "webinars":                     2,
    "microlearning":                2,
    "micro-learning":               2,
    "soft skills":                  2,
    "softskills":                   2,
    "compliance training":          2,
    "compliance trainingen":        2,
    "onboarding":                   2,
    "academie":                     2,

    # === Gewicht 1: Zwak signaal (alleen in combinatie waardevol) ===
    "management training":          1,
    "leiderschapstraining":         1,
    "persoonlijke ontwikkeling":    1,
    "professionele ontwikkeling":   1,

    # Sector-specifieke termen
    "gemeentelijke opleidingen":    2,
    "ambtenarentraining":           2,
    "overheidsacademie":            2,
    "zorgopleidingen":              2,
    "zorgtrainingen":               2,
    "BIG registratie":              2,
    "nascholing zorg":              2,
    "docentprofessionalisering":    2,
    "lerarentraining":              2,
    "onderwijsprofessionalisering": 2,
}

# Platte lijst van zoektermen (voor backwards-compat en regex filtering)
SEARCH_TERMS = list(TERM_WEIGHTS.keys())

# Sector-specifieke zoektermen (subset)
SECTOR_TERMS = [
    "gemeentelijke opleidingen",
    "ambtenarentraining",
    "overheidsacademie",
    "zorgopleidingen",
    "zorgtrainingen",
    "BIG registratie",
    "nascholing zorg",
    "docentprofessionalisering",
    "lerarentraining",
    "onderwijsprofessionalisering",
]

# Relevant CPV codes organized by category
CPV_CODES = {
    "software_systemen": [
        "48190000-6",  # Software voor educatieve doeleinden
        "48931000-3",  # Software voor opleidingen
        "72212190-7",  # Ontwikkeling educatieve software
        "72413000-8",  # Webdesign (leerportalen)
        "72260000-5",  # Software-gerelateerde diensten — gevonden in concurrenten-tenders
        "72000000-5",  # IT-diensten algemeen — gevonden in concurrenten-tenders
    ],
    "e_learning_content": [
        "80420000-4",  # E-learning diensten
        "80000000-4",  # Onderwijs en opleiding
        "80400000-8",  # Volwasseneneducatie
        "92312211-2",  # Schrijven lesmateriaal
    ],
    "leermiddelen": [
        "22114300-5",  # Leermiddelen
        "79990000-0",  # Zakelijke diensten (licenties)
    ],
    "trainingen": [
        "80500000-9",  # Opleidingsdiensten
        "80510000-2",  # Beroepsopleidingen
        "80511000-9",  # Personeelsopleidingen
        "80532000-2",  # Managementtrainingen
        "80570000-0",  # Persoonlijke ontwikkeling
        "80520000-5",  # Trainingsfaciliteitsdiensten — gevonden in concurrenten-tenders
    ],
}

# Flatten CPV codes for easy lookup
ALL_CPV_CODES = []
for category_codes in CPV_CODES.values():
    ALL_CPV_CODES.extend(category_codes)

# CPV code descriptions for display
CPV_DESCRIPTIONS = {
    "48190000-6": "Software voor educatieve doeleinden",
    "48931000-3": "Software voor opleidingen",
    "72212190-7": "Ontwikkeling educatieve software",
    "72413000-8": "Webdesign (leerportalen)",
    "72260000-5": "Software-gerelateerde diensten",
    "72000000-5": "IT-diensten",
    "80420000-4": "E-learning diensten",
    "80000000-4": "Onderwijs en opleiding",
    "80400000-8": "Volwasseneneducatie",
    "92312211-2": "Schrijven lesmateriaal",
    "22114300-5": "Leermiddelen",
    "79990000-0": "Zakelijke diensten (licenties)",
    "80500000-9": "Opleidingsdiensten",
    "80510000-2": "Beroepsopleidingen",
    "80511000-9": "Personeelsopleidingen",
    "80532000-2": "Managementtrainingen",
    "80570000-0": "Persoonlijke ontwikkeling",
    "80520000-5": "Trainingsfaciliteitsdiensten",
}

# Default settings
DEFAULT_CONTRACT_YEARS = 3  # Assumed contract duration
DEFAULT_LEAD_MONTHS = 4     # Months before republication to contact

# ===============================================
# KERNCONCURRENTEN (directe concurrenten — opgegeven door sales)
# ===============================================
# Tenders gewonnen door deze partijen = maximale relevantiescore (100)
# Dit zijn de sterkste leads: het contract loopt af, de organisatie gaat opnieuw aanbesteden.
#
# Structuur: { "weergavenaam": ["variatie1", "variatie2", ...] }
# De variaties zijn wat er in de TenderNed data kan staan als winnende partij.

CORE_COMPETITORS = {
    "Plusport": [
        "plusport",
        "plus-port",
        "plusport b.v.",
        "plusport bv",
        "plusport b.v",
    ],
    "GoodHabitz": [
        "goodhabitz",
        "good habitz",
        "goodhabitz b.v.",
        "goodhabitz bv",
        "goodhabitz b.v",
    ],
    "New Heroes": [
        "new heroes",
        "newheroes",
        "the new heroes",
        "new heroes b.v.",
        "new heroes bv",
        "newheroesgroup",
    ],
    "StudyTube": [
        "studytube",
        "study tube",
        "studytube b.v.",
        "studytube bv",
        "studytube b.v",
    ],
    "Courseware": [
        "courseware",
        "course ware",
        "courseware b.v.",
        "courseware bv",
        "courseware b.v",
    ],
    "Online Academie": [
        "online academie",
        "onlineacademie",
        "online-academie",
        "online academie b.v.",
        "online academie bv",
    ],
    "Uplearning": [
        "uplearning",
        "up learning",
        "up-learning",
        "uplearning b.v.",
        "uplearning bv",
    ],
}

# Platte lijst van alle kernconcurrent-variaties (voor snelle matching)
ALL_CORE_COMPETITOR_TERMS = []
for variants in CORE_COMPETITORS.values():
    ALL_CORE_COMPETITOR_TERMS.extend(variants)

# ===============================================
# OVERIGE CONCURRENTEN (LMS platforms / aanbieders die ook NL tenders winnen)
# ===============================================
# Minder direct dan de 7 kerncurrenten, maar wel relevante signalen.

SECONDARY_COMPETITORS = []

# Gecombineerde lijst voor backwards-compat (gebruikt door bestaande functies)
COMPETITORS = list(set(ALL_CORE_COMPETITOR_TERMS + SECONDARY_COMPETITORS))

# ===============================================
# NEGATIEVE KEYWORDS (uitsluitingslijst)
# ===============================================
NEGATIVE_KEYWORDS = [
    # Vacature-gerelateerd
    "medewerker",
    "vacature",
    "functie",
    "sollicitatie",
    "fte",
    "fulltime",
    "parttime",
    "part-time",
    "full-time",
    "dienstverband",
    "arbeidsovereenkomst",
    "werkzaam",
    "gezocht",
    "werving",
    "selectie",
    "teamleider",
    "coördinator",
    "manager gezocht",

    # Fysieke training (niet online)
    "klassikale training",
    "incompany trainer",
]

# ===============================================
# SECTOREN CONFIGURATIE
# ===============================================
SECTORS = {
    "overheid": {
        "priority": 3,
        "keywords": ["gemeente", "provincie", "rijksoverheid", "ministerie", "waterschap"],
        "description": "Partner van Bestuursacademie Nederland"
    },
    "zorg": {
        "priority": 3,
        "keywords": ["ziekenhuis", "ggz", "verpleging", "verzorging", "thuiszorg"],
        "description": "Zorgopleidingen en BIG-nascholing"
    },
    "onderwijs": {
        "priority": 3,
        "keywords": ["school", "universiteit", "hogeschool", "mbo", "primair onderwijs"],
        "description": "Docentprofessionalisering"
    },
    "jeugdzorg": {
        "priority": 2,
        "keywords": ["jeugdzorg", "jeugdhulp", "jeugdbescherming"],
        "description": "Specialistische trainingen jeugdzorg"
    },
    "kinderopvang": {
        "priority": 2,
        "keywords": ["kinderopvang", "bso", "kdv", "peuterspeelzaal"],
        "description": "Trainingen kinderopvang sector"
    },
    "retail": {
        "priority": 2,
        "keywords": ["retail", "winkel", "detailhandel"],
        "description": "Retail trainingen"
    },
    "logistiek": {
        "priority": 2,
        "keywords": ["logistiek", "transport", "warehousing", "supply chain"],
        "description": "Logistieke opleidingen"
    },
    "uitzend": {
        "priority": 2,
        "keywords": ["uitzendbureau", "uitzendorganisatie", "detachering", "flexwerk"],
        "description": "Trainingen voor uitzendbranche"
    },
}

# Priority thresholds (days until contact needed)
PRIORITY_THRESHOLDS = {
    "URGENT": 30,
    "HIGH": 90,
    "MEDIUM": 180,
    "LOW": float("inf"),
}

# Priority colors for visualization
PRIORITY_COLORS = {
    "URGENT": "#FF4B4B",
    "HIGH": "#FFA500",
    "MEDIUM": "#FFD700",
    "LOW": "#90EE90",
    "OVERDUE": "#8B0000",
    "UNKNOWN": "#808080",
}

# ===============================================
# AI ANALYSE CONFIGURATIE
# ===============================================
AI_CONFIG = {
    "max_days_in_past": 1825,       # Max 5 jaar oud (Fase 6: breed filter)
    "require_keyword_match": True,  # Moet eerst keyword/CPV match hebben
    "min_description_length": 50,
    "batch_size": 10,
    "relevance_threshold": 30,
}

# ===============================================
# DATASET CONFIGURATIE
# ===============================================
# Patroon voor het automatisch vinden van de lokale TenderNed dataset.
# Bestand staat lokaal op schijf (te groot voor git).
LOCAL_DATASET_PATTERN = "Dataset_Tenderned*.xlsx"
