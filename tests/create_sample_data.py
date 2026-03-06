"""
Create sample TenderNed data for testing the Streamlit app.
Run: python tests/create_sample_data.py
"""

import pandas as pd
from datetime import datetime, timedelta
import random

# Sample organizations
organizations = [
    "Gemeente Amsterdam",
    "Gemeente Rotterdam",
    "Ministerie van BZK",
    "Ministerie van OCW",
    "Rijkswaterstaat",
    "Belastingdienst",
    "UWV",
    "DUO",
    "Politie Nederland",
    "Stichting Onderwijs",
    "Waterschap Amstel",
    "Provincie Noord-Holland",
    "GGD Amsterdam",
    "Radboud Universiteit",
    "Erasmus MC",
]

# Mix of relevant and irrelevant tenders
tender_data = [
    # Relevant - LMS/E-learning
    ("LMS platform implementatie", "Aanbesteding voor nieuw learning management systeem voor medewerkers", "48190000-6"),
    ("E-learning modules ontwikkeling", "Ontwikkeling van e-learning content voor compliance trainingen", "80420000-4"),
    ("Leermanagementsysteem onderwijs", "LMS voor basisscholen in de regio", "48931000-3"),
    ("Online leerplatform", "Platform voor digitaal leren en kennisdeling", "48190000-6"),
    ("Blended learning programma", "Combinatie van online en klassikaal leren", "80420000-4"),
    ("E-learning bibliotheek licenties", "Toegang tot e-learning content bibliotheek", "80420000-4"),
    ("Auteurstool voor e-learning", "Authoring tool voor interne e-learning ontwikkeling", "72212190-7"),
    ("Opleidingsbroker diensten", "Intermediair voor opleidingen en cursussen", "80500000-9"),
    ("Digitale leermiddelen", "Aanschaf digitale leermaterialen", "22114300-5"),
    ("Personeelsopleidingen 2024", "Diverse trainingen voor personeel", "80511000-9"),

    # Irrelevant tenders (should be filtered out)
    ("Wegenbouw A12", "Onderhoud en renovatie snelweg A12", "45233120-6"),
    ("Catering diensten", "Cateringverzorging voor kantoorpand", "55520000-1"),
    ("Schoonmaakdiensten", "Dagelijkse schoonmaak kantoren", "90910000-9"),
    ("Kantoormeubilair", "Aanschaf bureaus en stoelen", "39130000-2"),
    ("IT hardware", "Laptops en monitors", "30213100-6"),
    ("Beveiliging", "Beveiligingsdiensten gebouw", "79710000-4"),
    ("Accountantsdiensten", "Jaarrekening controle", "79211000-6"),
    ("Groenvoorziening", "Onderhoud tuinen en plantsoenen", "77310000-6"),
    ("Verhuisdiensten", "Kantoorverhuizing", "60000000-8"),
    ("Drukwerk", "Drukken van folders en brochures", "79810000-5"),
]

def create_sample_excel(output_path: str, num_rows: int = 50):
    """Create sample TenderNed Excel file."""

    data = []
    base_date = datetime(2023, 1, 1)

    for i in range(num_rows):
        # Cycle through tender types
        title, description, cpv = tender_data[i % len(tender_data)]

        # Randomize dates
        pub_date = base_date + timedelta(days=random.randint(0, 730))
        award_date = pub_date + timedelta(days=random.randint(30, 120))
        contract_start = award_date + timedelta(days=random.randint(0, 30))
        contract_end = contract_start + timedelta(days=random.randint(365, 1460))

        # Random value
        value = random.choice([None, 25000, 50000, 100000, 250000, 500000, 1000000])

        data.append({
            "Titel": f"{title} - #{i+1}",
            "Omschrijving": description,
            "Publicatiedatum": pub_date.strftime("%Y-%m-%d"),
            "Aanbestedende_dienst": random.choice(organizations),
            "Plaats": random.choice(["Amsterdam", "Rotterdam", "Den Haag", "Utrecht", "Eindhoven"]),
            "CPV_code": cpv,
            "Gunningsdatum": award_date.strftime("%Y-%m-%d") if random.random() > 0.3 else None,
            "Startdatum": contract_start.strftime("%Y-%m-%d") if random.random() > 0.4 else None,
            "Einddatum": contract_end.strftime("%Y-%m-%d") if random.random() > 0.5 else None,
            "Waarde": value,
            "Valuta": "EUR" if value else None,
            "Status": random.choice(["Gegund", "Gepubliceerd", "Gesloten"]),
        })

    df = pd.DataFrame(data)
    df.to_excel(output_path, index=False, engine="openpyxl")
    print(f"Created {output_path} with {num_rows} sample tenders")
    return df


if __name__ == "__main__":
    # Create sample file
    create_sample_excel("tests/sample_tenderned_data.xlsx", num_rows=50)

    # Also create a small test file
    create_sample_excel("tests/sample_small.xlsx", num_rows=10)

    print("\nSample files created! Upload these to test the app.")
