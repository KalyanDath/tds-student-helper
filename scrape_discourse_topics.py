import requests
import json
import time
import re
from http.cookies import SimpleCookie

# Configuration
SEARCH_URL = "https://discourse.onlinedegree.iitm.ac.in/search.json"
QUERY = "#courses:tds-kb before:2025-04-14 after:2025-01-01 order:latest"
TOTAL_PAGES = 3
COOKIE_FILE = "cookie.txt"
OUTPUT_FILE = "topic_ids_and_slugs.json"

def load_cookie_dict():
    """Reads cookie.txt and returns a dictionary of cookies."""
    try:
        with open(COOKIE_FILE, "r") as f:
            raw = f.read().strip()
        cookie = SimpleCookie()
        cookie.load(raw.replace("; ", "\n"))  # Fix parsing for SimpleCookie
        return {key: morsel.value for key, morsel in cookie.items()}
    except Exception as e:
        print("❌ Error loading cookies:", e)
        return {}

def save_cookie_dict(cookie_dict):
    """Writes the cookie dictionary back to cookie.txt"""
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
    with open(COOKIE_FILE, "w") as f:
        f.write(cookie_str)

def update_forum_session_cookie(response, cookie_dict):
    """Extracts _forum_session from Set-Cookie and updates cookie_dict"""
    set_cookie_header = response.headers.get("set-cookie", "")
    match = re.search(r"_forum_session=([^;]+)", set_cookie_header)
    if match:
        new_value = match.group(1)
        cookie_dict["_forum_session"] = new_value
        save_cookie_dict(cookie_dict)
        print("🔁 Updated _forum_session cookie from response.")
    else:
        print("ℹ️ No new _forum_session cookie found in response.")

def fetch_all_topic_ids_and_slugs():
    cookie_dict = load_cookie_dict()
    topic_map = {}

    for page in range(1, TOTAL_PAGES + 1):
        print(f"📄 Fetching page {page}...")
        params = {
            "q": QUERY,
            "page": page
        }
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())

        response = requests.get(SEARCH_URL, params=params, headers={"cookie": cookie_header})

        if response.status_code != 200:
            print(f"❌ Page {page} failed: {response.status_code}")
            continue

        update_forum_session_cookie(response, cookie_dict)

        try:
            topics = response.json().get("topics", [])
            for topic in topics:
                topic_id = str(topic["id"])
                topic_slug = topic["slug"]
                topic_map[topic_id] = topic_slug
        except Exception as e:
            print(f"⚠️ Failed to parse topics on page {page}: {e}")

        time.sleep(1)  # Be polite

    return topic_map

def main():
    print("🚀 Starting scrape")
    topic_map = fetch_all_topic_ids_and_slugs()

    with open(OUTPUT_FILE, "w") as f:
        json.dump(topic_map, f, indent=2)

    print(f"✅ Saved {len(topic_map)} topic mappings to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
