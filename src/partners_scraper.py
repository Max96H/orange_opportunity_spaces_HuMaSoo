import requests
import time
from bs4 import BeautifulSoup
import sqlite3
from pathlib import Path

DB_PATH = Path("./data/signals.db")

PAGES_NUMBERS = {
    "cybersecurity": {"n": "1329", "expertise": True}, 
    "cx": {"n": "1327", "expertise": True},
    "cloud": {"n": "1260", "expertise": False},
    "ex": {"n": "1326", "expertise": True},
    "connectivity": {"n": "1234", "expertise": False},
    "smart_industries": {"n": "1271", "expertise": False}
    }

def init_db():
    """Ensure the database directory and table exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT,
                partner TEXT,
                UNIQUE(domain, partner_name)
            )
        """) 

def scrape_card_paragraphs(session: requests.Session, url: str) -> list[str]:

    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()  # Raise exception for 4xx/5xx HTTP errors
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    cards = soup.find_all("div", class_="card h-100 p-1 position-relative")
    print(f"Found {len(cards)} cards")
    
    extracted_texts = []

    for idx, card in enumerate(cards, start=1):
        target_p = card.find("p", class_="small m-0 p-0 mb-1")

        if target_p:
            p_text = target_p.get_text(strip=True)
            extracted_texts.append(p_text)
            print(f"[Card {idx}] Text: {p_text}")
        else:
            print(f"[Card {idx}] Target <p> tag not found.")

    return extracted_texts

def main():
    init_db()

    with sqlite3.connect(DB_PATH) as conn, requests.Session() as session:
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
        )
        cursor = conn.cursor()

        for domain, dom_dic in PAGES_NUMBERS.items():
            if dom_dic["expertise"]:
                filter = "business_needs"
            else:
                filter = "solutions"
            url = f"https://www.orange-business.com/en/about-us/partners?filter_{filter}%5B{dom_dic["n"]}%5D={dom_dic["n"]}#hub-views-exposed-form"
            results = scrape_card_paragraphs(session, url)
            print(f"\nTotal items extracted: {len(results)}")
            print(results)

            for partner in results:
                cursor.execute("""
                    INSERT OR IGNORE INTO partners (domain, partner) 
                    VALUES (?, ?)
                """, (domain, partner)
                )
            print(f"Results saved in db for {domain}")
            time.sleep(4)


if __name__ == "__main__":
    main()