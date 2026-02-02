import pandas as pd
import time
import random
import os
import re
import logging
import sys
import math
from bs4 import BeautifulSoup

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

# 🛑 IGNORE LIST: Dead ends
IGNORED_NAMES = {
    "Unknown", "Retired", "Without Club", "Disqualification", 
    "Career break", "Ban", "Rest", "TBD", "nan", "None"
}
# 0/NaN = Null, 75 = Unknown, 515 = Without Club, 123 = Retired
IGNORED_IDS = {0, 75, 515, 123}

# --- HELPERS ---
def get_start_year(season_str):
    try:
        parts = str(season_str).split('/')
        if len(parts[0]) == 2: return f"20{parts[0]}"
        return parts[0]
    except: return "2023"

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
    
    logger.info("🔧 Initializing Chrome Driver (Strict Rescue Mode)...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def get_historical_data(driver, club_id, season_str, club_name):
    year = get_start_year(season_str)
    url = f"https://www.transfermarkt.com/club/startseite/verein/{club_id}/saison_id/{year}"
    
    logger.info(f"   🕵️ Visiting: {club_name} ({season_str})")
    
    try:
        driver.get(url)
        try:
            WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CLASS_NAME, "data-header__details")))
        except: pass

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        
        league = None
        country = None

        # --- 1. EXTRACT HISTORICAL LEAGUE (STRICT) ---
        try:
            headlines = soup.select("h2.content-box-headline")
            for h2 in headlines:
                text = h2.get_text(strip=True)
                if "Table section" in text:
                    clean_text = text.replace("Table section", "").strip()
                    clean_text = re.sub(r'\s\d{2}/\d{2}$', '', clean_text)
                    clean_text = re.sub(r'\s\d{4}$', '', clean_text)
                    league = clean_text.strip()
                    break 
        except: pass

        # --- 2. EXTRACT COUNTRY ---
        try:
            flag = soup.select_one(".data-header__content img.flaggenrahmen")
            if flag and flag.get('title'):
                country = flag['title']
        except: pass

        return league, country

    except Exception as e:
        logger.error(f"      ❌ Error visiting page: {e}")
        return None, None

def main():
    if not os.path.exists(DATA_FILE):
        print(f"❌ Error: {DATA_FILE} not found.")
        return

    df = pd.read_csv(DATA_FILE, low_memory=False)
    
    bad_values = ["TBD", "Unknown", "nan"]
    unique_tasks = {} 
    
    print("🔍 Scanning rows... (Skipping Retired/Empty IDs)")

    def needs_fix(league_val, country_val):
        l_bad = str(league_val) in bad_values or pd.isna(league_val)
        c_bad = pd.isna(country_val) or str(country_val) in ["nan", ""]
        return l_bad or c_bad

    def is_valid_club(cid_raw, cname):
        # 1. Handle NaN / Float conversion safety
        try:
            if pd.isna(cid_raw): return False
            cid = int(cid_raw)
        except: return False
        
        # 2. Check Blocklists
        if cid in IGNORED_IDS: return False
        if str(cname) in IGNORED_NAMES: return False
        return True

    # Scan Origin
    for idx, row in df.iterrows():
        try:
            cid_raw = row['Origin_Club_ID']
            cname = row['Origin_Club']
            
            if is_valid_club(cid_raw, cname):
                cid = int(cid_raw)
                if needs_fix(row['Origin_League'], row['Origin_Country']):
                    unique_tasks[(cid, row['Season'])] = cname
        except: pass

    # Scan Destination
    for idx, row in df.iterrows():
        try:
            cid_raw = row['Destination_Club_ID']
            cname = row['Destination_Club']
            
            if is_valid_club(cid_raw, cname):
                cid = int(cid_raw)
                if needs_fix(row['Destination_League'], row['Destination_Country']):
                    unique_tasks[(cid, row['Season'])] = cname
        except: pass
        
    if not unique_tasks:
        print("✅ No valid missing data found!")
        return

    task_list = [(k[0], k[1], v) for k, v in unique_tasks.items()]
    task_list.sort(key=lambda x: x[0])
    
    print(f"📉 Filter Report:")
    print(f"   - Unique Valid Tasks: {len(task_list)}")
    
    print("\n🚑 Starting Strict Rescue Mission...")
    driver = init_driver()
    
    updates_made = 0
    try:
        for i, (cid, season, cname) in enumerate(task_list):
            league, country = get_historical_data(driver, cid, season, cname)
            
            if league or country:
                mask_o = (df['Origin_Club_ID'] == cid) & (df['Season'] == season)
                if league: df.loc[mask_o, 'Origin_League'] = league
                if country: df.loc[mask_o, 'Origin_Country'] = country
                
                mask_d = (df['Destination_Club_ID'] == cid) & (df['Season'] == season)
                if league: df.loc[mask_d, 'Destination_League'] = league
                if country: df.loc[mask_d, 'Destination_Country'] = country

                log_str = f"      ✅ Found:"
                if league: log_str += f" League='{league}'"
                if country: log_str += f" Country='{country}'"
                logger.info(log_str)
                updates_made += 1
            else:
                logger.warning(f"      ⚠️ No strict data found for {cname}")

            if i > 0 and i % 10 == 0:
                df.to_csv(DATA_FILE, index=False)
                
    except KeyboardInterrupt:
        print("\n🛑 Interrupted.")
    finally:
        driver.quit()
        df.to_csv(DATA_FILE, index=False)
        print(f"🏁 Done. Updated {updates_made} unique contexts.")

if __name__ == "__main__":
    main()