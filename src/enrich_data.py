import pandas as pd
import time
import random
import re
import os
import logging
import sys
import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

# --- SELENIUM IMPORTS ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger()

# --- CONSTANTS ---
DATA_FILE = "data/processed/transfer_base_table.csv"

# --- BROWSER SETUP ---
def init_driver():
    options = Options()
    options.add_argument("--headless=new") 
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    os.environ['WDM_LOG'] = '0'
    logging.getLogger('selenium').setLevel(logging.CRITICAL)
    
    logger.info("🔧 Initializing Chrome Driver...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

# --- HELPER FUNCTIONS ---
def clean_money(value_str):
    if not value_str or "-" in value_str: return 0.0
    val = value_str.lower().replace('€', '').strip()
    try:
        if 'm' in val: return float(val.replace('m', ''))
        elif 'k' in val: return float(val.replace('k', '')) / 1000
        else: return 0.0
    except: return 0.0

def get_season_year(season_str):
    try:
        parts = season_str.split('/')
        if len(parts[0]) == 2: return int(f"20{parts[0]}")
        return int(parts[0])
    except: return 0

def normalize_name(name):
    if not name: return ""
    n = name.lower()
    for word in ["fc", "fk", "cf", "csm", "acsm", "afc", "sc", "1948", "1923", "osk", "bucuresti", "constanta", "cluj", "univ.", "universitatea"]:
        n = n.replace(word, "")
    return n.strip()

# --- PHASE 1: PLAYER SCRAPER (SELENIUM) ---
def get_player_data_selenium(driver, player_id, player_name):
    url = f"https://www.transfermarkt.com/player/transfers/spieler/{player_id}"
    
    print(f"\n────────────────────────────────────────────────────────")
    logger.info(f"👤 Visiting: {player_name} (ID: {player_id})")
    
    try:
        driver.get(url)
        if "Challenge" in driver.title or "Cloudflare" in driver.title:
            logger.warning("   🛑 ACCESS BLOCKED: Cloudflare Challenge.")
            return None, None, [], 0.0
            
        try:
            WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CLASS_NAME, "tm-player-transfer-history-grid")))
        except: 
            logger.warning("   ⚠️ Transfer grid not found (New/Empty profile?).")

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

    except Exception as e:
        logger.error(f"   ❌ Browser Error: {e}")
        return None, None, [], 0.0

    dob, citizenship, current_mv = None, None, 0.0

    # ---------------------------------------------------------
    # 1. CAPTURE BIO (TARGETING TRANSFER PAGE HEADER)
    # ---------------------------------------------------------
    
    # Iterate through all list items in the header
    header_items = soup.select("li.data-header__label")
    
    for item in header_items:
        # Get the full text of the label to check what row we are on
        # (e.g. "Citizenship:   Slovakia")
        row_text = item.get_text(strip=True)
        
        # --- DATE OF BIRTH ---
        if "Date of birth" in row_text:
            val_span = item.select_one("span.data-header__content")
            if val_span:
                # Regex for date format
                match = re.search(r'\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2}', val_span.get_text())
                if match: dob = match.group(0)
                
                # Backup: Check for itemprop if regex failed
                if not dob:
                     itemprop = val_span.find("span", {"itemprop": "birthDate"})
                     if itemprop: 
                         match = re.search(r'\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2}', itemprop.get_text())
                         if match: dob = match.group(0)

        # --- CITIZENSHIP (Using your HTML structure) ---
        if "Citizenship" in row_text:
            val_span = item.select_one("span.data-header__content")
            if val_span:
                # 1. Look for images with class "flaggenrahmen" (Gold Standard)
                # HTML: <img ... title="Slovakia" ... class="flaggenrahmen">
                flags = val_span.select("img.flaggenrahmen")
                
                if flags:
                    # Extract 'title' attribute which contains clean country name
                    citizenship = " / ".join([img['title'] for img in flags if img.get('title')])
                
                # 2. Fallback: Just grab the text if no image found
                if not citizenship:
                    citizenship = re.sub(r'\s+', ' ', val_span.get_text(strip=True))

    # LOGGING RESULTS
    if dob or citizenship: 
        logger.info(f"   ✅ Bio Found: {dob} | {citizenship}")
    else:
        logger.warning(f"   ❌ Bio Failed! (Selector mismatch)")

    # ---------------------------------------------------------
    # 2. CAPTURE CURRENT MV
    # ---------------------------------------------------------
    try:
        mv_svelte = soup.select_one('div.current-value')
        if mv_svelte:
            current_mv = clean_money(mv_svelte.get_text(strip=True))
        
        if current_mv == 0.0:
            mv_box = soup.select_one('.data-header__market-value-wrapper')
            if mv_box:
                current_mv = clean_money(mv_box.get_text(strip=True))
    except: pass

    if current_mv > 0: logger.info(f"   💰 Current MV: €{current_mv}m")

    # ---------------------------------------------------------
    # 3. CAPTURE HISTORY
    # ---------------------------------------------------------
    history_data = []
    grids = soup.select(".tm-player-transfer-history-grid")
    
    for grid in grids:
        try:
            if "tm-player-transfer-history-grid--heading" in grid.get("class", []): continue
            if "tm-player-transfer-history-grid--sum" in grid.get("class", []): continue

            season_div = grid.select_one(".tm-player-transfer-history-grid__season")
            if not season_div: continue
            season = season_div.get_text(strip=True)
            if not re.search(r'\d{2}/\d{2}', season): continue

            mv_div = grid.select_one(".tm-player-transfer-history-grid__market-value")
            mv_val = clean_money(mv_div.get_text(strip=True) if mv_div else "-")

            old_div = grid.select_one(".tm-player-transfer-history-grid__old-club .tm-player-transfer-history-grid__club-link")
            old_club_name = old_div.get_text(strip=True) if old_div else "Unknown"

            history_data.append({
                'Season': season,
                'Season_Year': get_season_year(season),
                'Market_Value': mv_val,
                'Old_Club_Raw': old_club_name,
                'Old_Club_Norm': normalize_name(old_club_name)
            })
        except: continue
    
    logger.info(f"   📜 History Rows: {len(history_data)}")
    time.sleep(random.uniform(0.8, 1.2))
    return dob, citizenship, history_data, current_mv

# --- MAIN ---
def main():
    if not os.path.exists(DATA_FILE):
        print(f"❌ Error: {DATA_FILE} not found.")
        return

    df = pd.read_csv(DATA_FILE, low_memory=False)
    
    new_cols = ['Date_of_Birth', 'Citizenship', 'Market_Value_At_Transfer', 'Market_Value_Next_Season', 
                'Origin_Country', 'Destination_Country']
    for col in new_cols:
        if col not in df.columns: df[col] = None

    text_cols = ['Origin_Country', 'Destination_Country', 'Date_of_Birth', 'Citizenship', 'Origin_League', 'Destination_League']
    for col in text_cols:
        if col in df.columns: df[col] = df[col].astype("object")

    print("\n--- ENRICHMENT MENU ---")
    print("1. Enrich Players (Selenium)")
    print("2. Enrich Leagues (Requests)")
    choice = input("Select [1/2]: ").strip()

    if choice == '1':
        valid_id_mask = (df['TM_Player_ID'].notna()) & (df['TM_Player_ID'] != 0)
        # Aggressive Mask: If ANY key data is missing, re-process
        mask = (df['Date_of_Birth'].isna()) | \
               (df['Citizenship'].isna()) | \
               (df['Market_Value_At_Transfer'].isna()) | \
               (df['Market_Value_Next_Season'].isna()) 
               
        players_to_process = df.loc[mask & valid_id_mask, ['TM_Player_ID', 'Player_Name']].drop_duplicates(subset='TM_Player_ID')
        
        print(f"🚀 Processing {len(players_to_process)} players...")
        driver = init_driver()

        try:
            for idx, row in players_to_process.iterrows():
                try:
                    pid = int(row['TM_Player_ID'])
                    name = row['Player_Name']
                    
                    dob, cit, history, current_mv = get_player_data_selenium(driver, pid, name)
                    
                    # 1. Update Bio
                    if dob: df.loc[df['TM_Player_ID'] == pid, 'Date_of_Birth'] = dob
                    if cit: df.loc[df['TM_Player_ID'] == pid, 'Citizenship'] = cit

                    # 2. Update Market Values
                    if history:
                        player_rows = df[df['TM_Player_ID'] == pid]
                        for r_idx, csv_row in player_rows.iterrows():
                            target_season = csv_row['Season']
                            csv_norm = normalize_name(csv_row['Origin_Club'])
                            
                            candidates = [h for h in history if h['Season'] == target_season]
                            match = None
                            
                            if len(candidates) == 1:
                                match = candidates[0]
                            elif len(candidates) > 1:
                                for cand in candidates:
                                    if (cand['Old_Club_Norm'] in csv_norm) or (csv_norm in cand['Old_Club_Norm']):
                                        match = cand
                                        break
                                if not match: match = candidates[-1]
                            
                            if match:
                                df.at[r_idx, 'Market_Value_At_Transfer'] = match['Market_Value']
                                logger.info(f"      ✅ Matched MV: €{match['Market_Value']}m ({target_season})")

                                target_year = match['Season_Year']
                                future_entries = [h for h in history if h['Season_Year'] > target_year]
                                
                                if future_entries:
                                    next_val = future_entries[-1]['Market_Value']
                                    df.at[r_idx, 'Market_Value_Next_Season'] = next_val
                                    logger.info(f"      📈 Next Transfer MV: €{next_val}m")
                                else:
                                    if current_mv > 0:
                                        df.at[r_idx, 'Market_Value_Next_Season'] = current_mv
                                        logger.info(f"      🔮 Current MV used as Exit: €{current_mv}m")

                except Exception as e:
                    logger.error(f"   ⚠️ Error processing {row.get('Player_Name', 'Unknown')}: {e}")
                    continue

                # Save every row to verify immediately
                df.to_csv(DATA_FILE, index=False)
        
        except KeyboardInterrupt:
            print("\n🛑 Interrupted. Saving...")
        finally:
            driver.quit()
            df.to_csv(DATA_FILE, index=False)
            print("👋 Browser Closed & Data Saved.")
    
    elif choice == '2':
        pass

if __name__ == "__main__":
    main()