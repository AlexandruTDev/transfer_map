import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# We define the specific structure: (League Name, Season Label, URL)
# Note: TM use "saison_id/2023" for the 23/24 season.
LEAGUE_CONFIG = [
    # --- SUPERLIGA (RO1) ---
    ("Superliga", "25/26", "https://www.transfermarkt.com/superliga/startseite/wettbewerb/RO1/saison_id/2025"),
    ("Superliga", "24/25", "https://www.transfermarkt.com/superliga/startseite/wettbewerb/RO1/saison_id/2024"),
    ("Superliga", "23/24", "https://www.transfermarkt.com/superliga/startseite/wettbewerb/RO1/saison_id/2023"),
    ("Superliga", "22/23", "https://www.transfermarkt.com/superliga/startseite/wettbewerb/RO1/saison_id/2022"),
    ("Superliga", "21/22", "https://www.transfermarkt.com/superliga/startseite/wettbewerb/RO1/saison_id/2021"),
    ("Superliga", "20/21", "https://www.transfermarkt.com/superliga/startseite/wettbewerb/RO1/saison_id/2020"),
    ("Superliga", "19/20", "https://www.transfermarkt.com/superliga/startseite/wettbewerb/RO1/saison_id/2019"),

    # --- LIGA 2 (RO2) ---
    ("Liga 2", "25/26", "https://www.transfermarkt.com/liga-2/startseite/wettbewerb/RO2/saison_id/2025"),
    ("Liga 2", "24/25", "https://www.transfermarkt.com/liga-2/startseite/wettbewerb/RO2/saison_id/2024"),
    ("Liga 2", "23/24", "https://www.transfermarkt.com/liga-2/startseite/wettbewerb/RO2/saison_id/2023"),
    ("Liga 2", "22/23", "https://www.transfermarkt.com/liga-2/startseite/wettbewerb/RO2/saison_id/2022"),
    ("Liga 2", "21/22", "https://www.transfermarkt.com/liga-2/startseite/wettbewerb/RO2/saison_id/2021"),
    ("Liga 2", "20/21", "https://www.transfermarkt.com/liga-2/startseite/wettbewerb/RO2/saison_id/2020"),
    ("Liga 2", "19/20", "https://www.transfermarkt.com/liga-2/startseite/wettbewerb/RO2/saison_id/2019"),
]

def extract_clubs_from_table(league_name, season_label, url):
    print(f"🔎 Scanning {league_name} {season_label}...")
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table', class_='items')
    if not table: return []

    found_entries = []
    rows = table.find_all('tr')
    
    for row in rows:
        # Find Club Link
        link_tag = row.find('a', class_='vereinprofil_tooltip')
        if not link_tag:
            link_tag = row.find('a', href=re.compile(r'/verein/'))
        
        if link_tag:
            href = link_tag['href'] # /fcsb/startseite/verein/301
            
            # 1. Get ID and Slug
            id_match = re.search(r'/verein/(\d+)', href)
            if not id_match: continue
            club_id = id_match.group(1)
            club_slug = href.strip('/').split('/')[0]
            
            # 2. Clean Name
            # Use 'title' if available, else slug. Replace special chars for safety.
            raw_name = link_tag.get('title', club_slug)
            club_name = raw_name.replace('â', 'a').strip()

            # 3. Build URL
            transfer_url = f"https://www.transfermarkt.com/{club_slug}/alletransfers/verein/{club_id}"

            found_entries.append({
                'Club_Name': club_name,
                'Club_ID': club_id,
                'Transfer_URL': transfer_url,
                'League': league_name,
                'Season': season_label
            })

    time.sleep(0.5)
    return found_entries

if __name__ == "__main__":
    all_entries = []
    
    # 1. Scrape all configured seasons
    for league, season, url in LEAGUE_CONFIG:
        entries = extract_clubs_from_table(league, season, url)
        all_entries.extend(entries)
    
    # 2. Create the League History Map (Club + Season -> League)
    df_history = pd.DataFrame(all_entries)
    df_history = df_history[['Club_Name', 'Season', 'League']].drop_duplicates()
    df_history.to_csv("data/club_league_history.csv", index=False)
    print(f"✅ Generated League History: {len(df_history)} rows saved to 'data/club_league_history.csv'")

    # 3. Create the Unique Club URL List (for the scraper)
    df_urls = pd.DataFrame(all_entries)
    # We only need one URL per club (deduplicate by ID)
    df_urls = df_urls[['Club_Name', 'Club_ID', 'Transfer_URL']].drop_duplicates(subset=['Club_ID'])
    df_urls.to_csv("data/club_urls_list.csv", index=False)
    print(f"✅ Generated Scraping List: {len(df_urls)} unique clubs saved to 'data/club_urls_list.csv'")