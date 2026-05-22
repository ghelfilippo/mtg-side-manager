"""MTGGoldfish Pauper metagame scraping."""
import re
import httpx
from bs4 import BeautifulSoup

METAGAME_URL = "https://www.mtggoldfish.com/metagame/pauper/full#paper"
BASE_URL = "https://www.mtggoldfish.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8",
    "Referer": "https://www.google.com/",
}

# Maps MTGGoldfish mana symbol CSS class -> our color code
MANA_CSS_TO_COLOR = {"ms-w": "W", "ms-u": "U", "ms-b": "B", "ms-r": "R", "ms-g": "G"}
DEFAULT_MIN_META_SHARE = 0.2


async def fetch_meta(min_share: float = DEFAULT_MIN_META_SHARE) -> dict:
    """Scrape MTGGoldfish Pauper metagame page and return structured data."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        r = await client.get(METAGAME_URL, headers=HEADERS)

    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}", "decks": []}

    soup = BeautifulSoup(r.text, "html.parser")
    tiles = soup.find_all("div", class_="archetype-tile")

    decks = []
    for tile in tiles:
        try:
            arch_id = tile.get("id", "")

            # Image URL from card-image-tile style
            img_div = tile.find("div", class_="card-image-tile")
            image_url = ""
            if img_div:
                m = re.search(r"url\('([^']+)'\)", img_div.get("style", ""))
                if m:
                    image_url = m.group(1)

            # Archetype page path
            link_a = tile.find("a", class_="card-image-tile-link-overlay")
            arch_path = link_a["href"] if link_a else ""
            arch_url = BASE_URL + arch_path if arch_path else ""

            # Deck name: prefer paper link
            name = ""
            paper_a = tile.find("span", class_="deck-price-paper")
            if paper_a:
                a = paper_a.find("a")
                if a:
                    name = a.get_text(strip=True)
            if not name:
                online_a = tile.find("span", class_="deck-price-online")
                if online_a:
                    a = online_a.find("a")
                    if a:
                        name = a.get_text(strip=True)

            # Meta share % — text looks like "META%10.1%(158)"
            pct_div = tile.find("div", class_=re.compile("metagame-percentage"))
            meta_share = 0.0
            if pct_div:
                pct_text = pct_div.get_text()
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", pct_text)
                if m:
                    meta_share = float(m.group(1))

            # Filter by minimum meta share
            if meta_share < min_share:
                continue

            # Colors from mana cost icons
            colors = []
            for i in tile.find_all("i", class_=True):
                for cls in i.get("class", []):
                    if cls in MANA_CSS_TO_COLOR:
                        c = MANA_CSS_TO_COLOR[cls]
                        if c not in colors:
                            colors.append(c)

            if not name:
                continue

            deck_id = f"goldfish-{arch_id}" if arch_id else f"goldfish-{re.sub(r'[^a-z0-9]+', '-', name.lower())}"

            decks.append({
                "id": deck_id,
                "name": name,
                "category": "Aggro",      # default, user can change
                "meta_share": meta_share,
                "image_url": image_url,
                "arch_url": arch_url,
                "colors": colors,
                "included": True,
                "source": "mtggoldfish",
            })

        except Exception:
            continue

    # Sort by meta share descending
    decks.sort(key=lambda d: d["meta_share"], reverse=True)
    return {"decks": decks, "source_url": METAGAME_URL}
