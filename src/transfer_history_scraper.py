import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
import os
import urllib.parse

# --- CONFIGURATION ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

RELEVANT_SEASONS = [
    "19/20", "20/21", "21/22", "22/23", "23/24", "24/25", "25/26"
]

# --- LOAD NAME MAPPING ---
NAME_MAP = {}
try:
    map_df = pd.read_csv("data/config/club_name_mapping.csv")
    NAME_MAP = pd.Series(map_df.Standard_Name.values, index=map_df.Variant_Name).to_dict()
    print(f"✅ Loaded Name Mapping ({len(NAME_MAP)} aliases).")
except FileNotFoundError:
    print("⚠️ Warning: Name mapping file not found.")

# --- LOAD LEAGUE HISTORY ---
LEAGUE_LOOKUP = {}
try:
    history_df = pd.read_csv("data/raw/club_league_history.csv")
    for _, row in history_df.iterrows():
        key = (row['Club_Name'].strip(), row['Season'].strip())
        LEAGUE_LOOKUP[key] = row['League']
    print(f"✅ Loaded League History ({len(LEAGUE_LOOKUP)} records).")
except FileNotFoundError:
    print("⚠️ Warning: League history file not found.")

def standardize_name(name):
    if not name: return "Unknown"
    name = name.strip()
    return NAME_MAP.get(name, name)

def get_league_context(raw_name, season):
    std_name = standardize_name(raw_name)
    if (std_name, season) in LEAGUE_LOOKUP:
        return LEAGUE_LOOKUP[(std_name, season)]
    return "TBD"

def extract_id_from_url(url):
    """Extracts numeric ID from TM URL: .../verein/1234/..."""
    if not url: return None
    match = re.search(r'/verein/(\d+)', url)
    return match.group(1) if match else None

def clean_money(value_str):
    if not value_str or "-" in value_str: return 0.0
    val = value_str.lower().replace('€', '').strip()
    if 'loan fee:' in val: val = val.split(':')[-1].strip()
    try:
        if 'm' in val: return float(val.replace('m', ''))
        elif 'k' in val: return float(val.replace('k', '')) / 1000
        else: return 0.0
    except: return 0.0

def scrape_complete_history(club_name, club_url):
    print(f"🔄 Scraping {club_name}...")
    
    # 1. Get Focus Club ID (from the URL we are visiting)
    focus_club_id = extract_id_from_url(club_url)
    
    try:
        response = requests.get(club_url, headers=HEADERS)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    transfers = []
    boxes = soup.find_all('div', class_='box')

    for box in boxes:
        headline = box.find('h2', class_='content-box-headline')
        if not headline: continue
        headline_text = headline.get_text(strip=True)

        # Check Season
        season_match = re.search(r'\d{2}/\d{2}', headline_text)
        if not season_match: continue
        season = season_match.group(0)
        if season not in RELEVANT_SEASONS: continue

        # Check Direction
        is_arrival = False
        if "Arrivals" in headline_text or "Zugänge" in headline_text: is_arrival = True
        elif "Departures" in headline_text or "Abgänge" in headline_text: pass
        else: continue

        table = box.find('table')
        if not table: continue
        
        rows = table.find_all('tr')
        for row in rows:
            if row.parent.name != 'tbody': continue
            
            # --- PLAYER ---
            player_cell = row.find('td', class_='hauptlink')
            if not player_cell: continue
            player_link = player_cell.find('a')
            if not player_link: continue
            player_name = player_link.get_text(strip=True)
            # Player ID
            tm_player_id = None
            if player_link.get('href'):
                id_match = re.search(r'/spieler/(\d+)', player_link['href'])
                if id_match: tm_player_id = id_match.group(1)

            # --- PARTNER CLUB ---
            partner_cell = row.find('td', class_='no-border-links')
            if not partner_cell: continue
            
            # Name
            partner_name_raw = partner_cell.get_text(strip=True)
            
            # ID (The Magic Step ✨)
            partner_id = None
            partner_link_tag = partner_cell.find('a')
            if partner_link_tag and partner_link_tag.get('href'):
                partner_id = extract_id_from_url(partner_link_tag['href'])

            # --- FEE ---
            fee_cell = row.find_all('td', class_='rechts')
            fee_raw = fee_cell[0].get_text(strip=True) if fee_cell else "-"
            fee_clean = fee_raw.replace('€', '').strip()
            fee_val = clean_money(fee_raw)
            
            t_type = "Permanent"
            if "loan" in fee_raw.lower(): t_type = "Loan"
            if "free" in fee_raw.lower(): t_type = "Free Transfer"

            # --- MAPPING ---
            known_club_league = get_league_context(club_name, season)
            # We still try to look up the partner league if it's a known Romanian club
            partner_league = get_league_context(partner_name_raw, season)
            
            std_partner = standardize_name(partner_name_raw)
            std_focus = standardize_name(club_name)

            if is_arrival:
                transfers.append({
                    'TM_Player_ID': tm_player_id,
                    'Player_Name': player_name,
                    'Season': season,
                    'Origin_Club': std_partner,
                    'Origin_Club_ID': partner_id, # NEW
                    'Origin_League': partner_league,
                    'Destination_Club': std_focus,
                    'Destination_Club_ID': focus_club_id, # NEW
                    'Destination_League': known_club_league,
                    'Fee_Raw': fee_clean,
                    'Fee_Est_M': fee_val,
                    'Transfer_Type': t_type
                })
            else:
                transfers.append({
                    'TM_Player_ID': tm_player_id,
                    'Player_Name': player_name,
                    'Season': season,
                    'Origin_Club': std_focus,
                    'Origin_Club_ID': focus_club_id, # NEW
                    'Origin_League': known_club_league,
                    'Destination_Club': std_partner,
                    'Destination_Club_ID': partner_id, # NEW
                    'Destination_League': partner_league,
                    'Fee_Raw': fee_clean,
                    'Fee_Est_M': fee_val,
                    'Transfer_Type': t_type
                })

    time.sleep(random.uniform(1, 2))
    return transfers

if __name__ == "__main__":
    try:
        clubs_df = pd.read_csv("data/raw/club_urls_list.csv")
        club_list = clubs_df.to_dict('records')
    except FileNotFoundError:
        print("❌ Error: Run get_club_urls.py first!")
        exit()

    all_data = []
    print(f"🚀 Starting ID-Enhanced Scraper ({len(club_list)} clubs)...")
    
    for entry in club_list:
        club = entry['Club_Name']
        url = entry['Transfer_URL']
        data = scrape_complete_history(club, url)
        all_data.extend(data)
        print(f"✅ {club}: {len(data)} moves.")
    
    df = pd.DataFrame(all_data)
    # Dedupe including IDs
    df.drop_duplicates(subset=['TM_Player_ID', 'Season', 'Origin_Club', 'Destination_Club'], inplace=True)
    
    os.makedirs('data/processed', exist_ok=True)
    df.to_csv("data/processed/transfer_base_table.csv", index=False)
    print("\n🏁 Done. IDs captured.")