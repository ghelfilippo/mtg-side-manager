"""MTGTOP8 Pauper meta scraping."""
import re
import httpx
from bs4 import BeautifulSoup

FORMAT_URL = "https://mtgtop8.com/format?f=PAU"
ARCH_URL = "https://mtgtop8.com/archetype?a={arch_id}&meta={meta_id}&f=PAU"
EVENT_URL = "https://mtgtop8.com{path}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


async def fetch_meta() -> dict:
    """Scrape MTGTOP8 Pauper format page and return structured meta data."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        r = await client.get(FORMAT_URL, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")
    decks = []
    meta_id = None
    current_category = "Aggro"

    # MTGTOP8 groups archetypes under bold category headers before their links
    # Walk all elements to detect both section headers and archetype links
    for elem in soup.find_all(["div", "td", "a"]):
        text = elem.get_text(strip=True)

        # Detect category section headers (exact match)
        if text in ("Aggro", "Control", "Combo"):
            current_category = text
            continue

        # Detect archetype links
        if elem.name == "a":
            href = elem.get("href", "")
            arch_match = re.search(r"archetype\?a=(\d+)", href)
            if not arch_match:
                continue

            arch_id = arch_match.group(1)
            meta_match = re.search(r"meta=(\d+)", href)
            if meta_match:
                meta_id = meta_match.group(1)

            name = elem.get_text(strip=True)
            if not name:
                continue

            # Meta share % is in the next sibling text or a nearby td
            pct = 0.0
            parent = elem.parent
            if parent:
                parent_text = parent.get_text()
                pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", parent_text)
                if pct_match:
                    pct = float(pct_match.group(1))

            deck_id = f"mtgtop8-{arch_id}"
            # avoid duplicates
            if any(d["id"] == deck_id for d in decks):
                continue

            decks.append({
                "id": deck_id,
                "name": name,
                "category": current_category,
                "meta_share": pct,
                "archetype_id": arch_id,
                "meta_id": meta_id,
                "top_decklist_url": None,
                "included": True,
            })

    return {"meta_id": meta_id, "decks": decks}


async def fetch_top_decklist(arch_id: str, meta_id: str) -> dict:
    """Fetch the top decklist for an archetype, return card list."""
    if not meta_id:
        return {"error": "No meta_id available"}

    url = ARCH_URL.format(arch_id=arch_id, meta_id=meta_id)
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        r = await client.get(url, headers=HEADERS)

    soup = BeautifulSoup(r.text, "html.parser")

    # Find first event/deck link
    deck_link = None
    for a in soup.find_all("a", href=re.compile(r"event\?e=\d+&d=\d+")):
        deck_link = a["href"]
        break

    if not deck_link:
        return {"error": "No decklist found", "source_url": url}

    full_url = EVENT_URL.format(path=deck_link if deck_link.startswith("/") else "/" + deck_link)
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        r2 = await client.get(full_url, headers=HEADERS)

    soup2 = BeautifulSoup(r2.text, "html.parser")

    main_deck = []
    sideboard = []
    current_section = "main"

    for div in soup2.find_all("div", class_=re.compile(r"deck_line")):
        text = div.get_text(strip=True)
        if "sideboard" in text.lower():
            current_section = "sideboard"
            continue
        qty_match = re.match(r"^(\d+)\s+(.+)$", text)
        if qty_match:
            qty = int(qty_match.group(1))
            name = qty_match.group(2).strip()
            entry = {"quantity": qty, "name": name}
            if current_section == "sideboard":
                sideboard.append(entry)
            else:
                main_deck.append(entry)

    # Fallback: look for quantity-prefixed lines anywhere
    if not main_deck:
        for elem in soup2.find_all(string=re.compile(r"^\d+ ")):
            m = re.match(r"^(\d+)\s+(.+)$", elem.strip())
            if m:
                main_deck.append({"quantity": int(m.group(1)), "name": m.group(2)})

    return {
        "source_url": full_url,
        "main_deck": main_deck,
        "sideboard": sideboard,
    }
