import pandas as pd
import os

def audit_club_names():
    # Load the final dataset
    try:
        df = pd.read_csv("data/processed/transfer_base_table.csv")
    except FileNotFoundError:
        print("❌ Error: Processed data not found. Run scraper first.")
        return

    # Collect all names from both Origin and Destination
    origins = df['Origin_Club'].unique()
    destinations = df['Destination_Club'].unique()
    
    # Combine and deduplicate
    all_clubs = set(origins) | set(destinations)
    
    # Sort alphabetically (Crucial for spotting duplicates next to each other)
    sorted_clubs = sorted([str(x) for x in all_clubs])
    
    # Save to a text file for easy manual review
    output_path = "data/processed/unique_club_names.txt"
    os.makedirs('data/processed', exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"--- UNIQUE CLUBS FOUND: {len(sorted_clubs)} ---\n")
        f.write("Review this list for duplicates (e.g. 'Minaur' vs 'Minaur Baia Mare')\n")
        f.write("If you find duplicates, add them to src/create_mapping.py\n\n")
        
        for club in sorted_clubs:
            f.write(f"{club}\n")
            
    print(f"✅ Audit Complete. Found {len(sorted_clubs)} unique club names.")
    print(f"📄 Open '{output_path}' to review the list.")

if __name__ == "__main__":
    audit_club_names()