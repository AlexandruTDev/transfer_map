import pandas as pd
import os

# KNOWN_ALIASES: Key = Variant found in Scraper, Value = Standard Name
KNOWN_ALIASES = {
    # --- SUPERLIGA GIANTS ---
    "FCSB": "FCSB",
    
    # DINAMO 1948 (The Superliga Club)
    "FC Dinamo": "FC Dinamo 1948",
    "Dinamo": "FC Dinamo 1948",
    "Dinamo Bucharest": "FC Dinamo 1948",
    
    # CS DINAMO (The Ministry Club) - DO NOT MERGE WITH ACS FC OR FC DINAMO 1948
    "CS Dinamo Buc.": "CS Dinamo Bucuresti",
    "CS Dinamo": "CS Dinamo Bucuresti",
    
    # ACS FC DINAMO (Nicolae Badea's Club) - KEEP SEPARATE
    "ACS FC Dinamo": "ACS FC Dinamo Bucuresti",

    # RAPID
    "Rapid": "FC Rapid 1923",
    "Rapid Bucharest": "FC Rapid 1923",
    
    # CRAIOVA (Rotaru - CS)
    "Univ. Craiova": "CS Universitatea Craiova",
    "CS U Craiova": "CS Universitatea Craiova",
    "Universitatea Craiova": "CS Universitatea Craiova",
    
    # CRAIOVA (Mititelu - FCU)
    "FC U Craiova": "FC U Craiova 1948",
    "FCU Craiova": "FC U Craiova 1948",
    
    # U CLUJ
    "U Cluj": "FC Universitatea Cluj",
    "Universitatea Cluj": "FC Universitatea Cluj",
    
    # FARUL / VIITORUL
    "Farul": "FCV Farul Constanta",
    "FCV Farul": "FCV Farul Constanta",
    "FC Farul 1920": "FCV Farul Constanta",
    "Viitorul": "FC Viitorul Constanta", 
    "FC Viitorul": "FC Viitorul Constanta",
    "Academia Hagi": "FC Viitorul Constanta",
    
    # --- LIGA 2 & OTHERS ---
    "Sepsi": "Sepsi OSK Sf. Gheorghe",
    "Sepsi OSK": "Sepsi OSK Sf. Gheorghe",
    "Otelul": "SC Otelul Galati",
    "Otelul Galati": "SC Otelul Galati",
    "Petrolul": "Petrolul Ploiesti",
    "FC Arges": "ACSC FC Arges",
    "Arges": "ACSC FC Arges",
    "UTA": "UTA Arad",
    "Hermannstadt": "FC Hermannstadt",
    "Botosani": "FC Botosani",
    "Voluntari": "FC Voluntari",
    "Poli Iasi": "ACSM Politehnica Iasi",
    "ACSM Poli Iasi": "ACSM Politehnica Iasi",
    "CSM Politehnica Iasi": "ACSM Politehnica Iasi",
    "Chindia": "AFC Chindia Targoviste",
    "Mioveni": "CS Mioveni",
    "Slobozia": "AFC Unirea 04 Slobozia",
    "Unirea Slobozia": "AFC Unirea 04 Slobozia",
    "Gloria Buzau": "ASFC Buzau (2016-2025)",
    "FC Buzau": "ASFC Buzau (2016-2025)",
    "SCM Gloria Buzau": "ASFC Buzau (2016-2025)",
    "Minaur": "Minaur Baia Mare",
    "CS Minaur": "Minaur Baia Mare",
    "Metaloglobus": "FC Metaloglobus Bucharest",
    "Metaloglob.": "FC Metaloglobus Bucharest",
    "Concordia": "Concordia Chiajna",
    "M. Ciuc": "FK Csikszereda Miercurea Ciuc",
    "FK Csikszereda": "FK Csikszereda Miercurea Ciuc",
    "Selimbar": "CSC 1599 Selimbar",
    "CSC Selimbar": "CSC 1599 Selimbar",
    "Dumbravita": "CSC Dumbravita",
    "Resita": "ACSM Resita",
    "CSM Resita": "ACSM Resita",
    "Slatina": "CSM Slatina",
    "Corvinul": "Corvinul Hunedoara",
    "Steaua": "CSA Steaua",
    "Metalul Buzau": "AFC Metalul Buzau",
    "Ceahlaul": "CSM Ceahlaul Piatra Neamt",
    "Unirea Dej": "Unirea Dej",
    "Viitorul Tg.Jiu": "Viitorul Pandurii Targu Jiu (- 2024)",
    "FC Bihor": "FC Bihor 1902",
    "Astra Giur.": "Astra Giurgiu (- 2024)",
    "Astra Giurgiu": "Astra Giurgiu (- 2024)",
    "Gaz Metan": "Gaz Metan Medias (- 2022)",
    "Academica": "Academica Clinceni",
    "Academica Clince": "Academica Clinceni",
    "D. Calarasi": "Dunarea Calarasi",
    "Ripensia": "Ripensia Timisoara",
    "Aerostar": "Aerostar Bacau",
    "AFC Turris": "AFC Turris-Oltul Turnu Magurele (- 2021)",
    "Progresul Sp.": "AFC Progresul 1944 Spartac",

    # --- MISSING & DISCREPANCY FIXES (Added from discussion) ---
    
    # BRASOV
    "Corona Bv.": "Corona Brasov",
    "FC Brasov-SR": "SR Brasov",
    
    # BRAILA (Standardizing the U)
    "Dacia U. Braila": "Dacia Unirea Braila",

    # RECEA (The 2020/21 Liga 2 Club)
    "Comuna Recea": "ACS Fotbal Comuna Recea (- 2021)",
    "Ac. Recea": "ACS Fotbal Comuna Recea (- 2021)",
    "ACS Fotbal Comuna Recea": "ACS Fotbal Comuna Recea (- 2021)",

    # BISTRITA
    "FC Gl. Bistrita": "Gloria Bistrita",

    # SATU MARE
    "CSM Olimpia SM": "CSM Olimpia Satu Mare",
    "Olimpia SM": "CSM Olimpia Satu Mare",

    # FOCSANI
    "CSM Focsani": "CSM Focsani 2007",

    # PANDURII (Old)
    "Pandurii": "Pandurii Targu Jiu (- 2022)",

    # TIMISOARA (Separation)
    "SSU Poli": "SSU Politehnica Timisoara",
    "Poli Timisoara": "SSU Politehnica Timisoara",
    "CNP Timisoara": "CNP Timisoara", # Federation Academy - DO NOT MERGE
    
    # --- YOUTH / SECOND TEAM HANDLING ---
    # We standardize the naming format so they don't look like duplicates of the parent
    
    # FCSB
    "FCSB II": "FCSB II",
    
    # DINAMO
    "Dinamo II": "FC Dinamo 1948 II",
    "CS D. Buk. U17": "CS Dinamo Bucuresti U17",
    "CS Dinamo U19": "CS Dinamo Bucuresti U19",

    # CRAIOVA
    "Univ. Craiova II": "CS Universitatea Craiova II",
    "CS U Craiova II": "CS Universitatea Craiova II",
    "CS U Craiova YL": "CS Universitatea Craiova U19",

    # CLINCENI
    "Clinceni II": "Academica Clinceni II",
    "Clinceni U19": "Academica Clinceni U19",

    # CHIAJNA
    "Chiajna II": "Concordia Chiajna II",
    "Chiajna U18": "Concordia Chiajna U18",

    # VOLUNTARI
    "Voluntari U18": "FC Voluntari U18",
    "FC Voluntari II": "FC Voluntari II",

    # U CLUJ
    "U Cluj II": "FC Universitatea Cluj II",
    "U Cluj U18": "FC Universitatea Cluj U18",
    "U Cluj Youth": "FC Universitatea Cluj Youth",

    # GAZ METAN
    "Gaz Metan II": "Gaz Metan Medias II",
    "Gaz Metan U19": "Gaz Metan Medias U19",

    # CSIKSZEREDA
    "Csikszereda II": "FK Csikszereda Miercurea Ciuc II",
    "Csikszereda U19": "FK Csikszereda Miercurea Ciuc U19",

    # RIPENSIA
    "Ripensia U19": "Ripensia Timisoara U19",

    # DUNAREA CALARASI
    "D. Calarasi U19": "Dunarea Calarasi U19",
    "DU Braila U19": "Dacia Unirea Braila U19",

    # POLI TIMISOARA
    "Poli Tim. U19": "SSU Politehnica Timisoara U19",

    # SEPSI
    # Senior Team: Must match Transfermarkt League Table name exactly to get "Superliga"
    "Sepsi": "Sepsi OSK Sf. Gheorghe",
    "Sepsi OSK": "Sepsi OSK Sf. Gheorghe",
    
    # Youth/Second Teams: We can normalize these to the shorter "Sepsi OSK" format you prefer
    "Sepsi OSK II": "Sepsi OSK II", # Standardized short name
    "Sepsi U19": "Sepsi OSK U19",   # Standardized short name
    "Sepsi OSK Sf. Gheorghe U19": "Sepsi OSK U19", # Catching the long variant too
}

def create_initial_map():
    df_map = pd.DataFrame(list(KNOWN_ALIASES.items()), columns=['Variant_Name', 'Standard_Name'])
    os.makedirs('data/config', exist_ok=True)
    output_path = "data/config/club_name_mapping.csv"
    df_map.to_csv(output_path, index=False)
    print(f"✅ Created Mapping File: {output_path}")
    print(f"   Contains {len(df_map)} aliases.")

if __name__ == "__main__":
    create_initial_map()