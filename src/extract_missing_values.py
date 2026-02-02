import pandas as pd
import os

# --- CONFIG ---
INPUT_FILE = "data/processed/transfer_base_table.csv"
OUTPUT_FILE = "data/manual_review_list.csv"

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} not found.")
        return

    df = pd.read_csv(INPUT_FILE, low_memory=False)
    
    # Dictionary to store unique missing contexts
    missing_map = {}
    
    bad_values = ["TBD", "Unknown", "nan"]

    def is_bad(val):
        return pd.isna(val) or str(val) in bad_values or str(val).strip() == ""

    print("🔍 Scanning for remaining TBDs...")
    
    # --- 1. SCAN ORIGIN ---
    for _, row in df.iterrows():
        if is_bad(row['Origin_League']):
            try:
                # Handle potential float/NaN IDs safely
                cid_raw = row['Origin_Club_ID']
                if pd.isna(cid_raw): continue
                cid = int(cid_raw)
                
                # Filter ignored IDs
                if cid in [0, 75, 515, 123]: continue 
                
                key = (cid, row['Season'])
                if key not in missing_map:
                    missing_map[key] = {
                        'Club_ID': cid,  # Store explicitly here
                        'Club_Name': row['Origin_Club'],
                        'Season': row['Season'],
                        'Existing_Country': row['Origin_Country'],
                        'Occurrences': 0
                    }
                missing_map[key]['Occurrences'] += 1
            except: pass

    # --- 2. SCAN DESTINATION ---
    for _, row in df.iterrows():
        if is_bad(row['Destination_League']):
            try:
                cid_raw = row['Destination_Club_ID']
                if pd.isna(cid_raw): continue
                cid = int(cid_raw)
                
                if cid in [0, 75, 515, 123]: continue

                key = (cid, row['Season'])
                if key not in missing_map:
                    missing_map[key] = {
                        'Club_ID': cid,  # Store explicitly here
                        'Club_Name': row['Destination_Club'],
                        'Season': row['Season'],
                        'Existing_Country': row['Destination_Country'],
                        'Occurrences': 0
                    }
                missing_map[key]['Occurrences'] += 1
            except: pass

    # --- 3. SAFE DATAFRAME CREATION ---
    if not missing_map:
        print("✅ No TBD values found! Your data is already clean.")
        return

    # Convert dictionary values directly to a list (Flattens the structure)
    data_list = list(missing_map.values())
    review_df = pd.DataFrame(data_list)
    
    # Define column order
    cols = ['Club_ID', 'Club_Name', 'Season', 'Existing_Country', 'Occurrences']
    review_df = review_df[cols]
    
    # Add empty column for your manual input
    review_df['New_League'] = ""
    
    # Sort by Occurrences (Fix the biggest impact items first!)
    review_df = review_df.sort_values(by='Occurrences', ascending=False)

    print(f"\n📊 Found {len(review_df)} unique contexts to review.")
    print(f"💾 Saving to {OUTPUT_FILE}...")
    review_df.to_csv(OUTPUT_FILE, index=False)
    print("✅ Done. Open the CSV in Excel, fill 'New_League', and save.")

if __name__ == "__main__":
    main()