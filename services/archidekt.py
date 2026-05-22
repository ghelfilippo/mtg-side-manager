"""Archidekt folder scraping and deck API."""
import asyncio
import json
import re
import httpx

FOLDER_URL = "https://archidekt.com/folders/1123156"
API_BASE = "https://archidekt.com/api/decks"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


async def fetch_folder_deck_ids() -> list[dict]:
    """Scrape folder page and return [{id, name}] for all decks."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        r = await client.get(FOLDER_URL, headers=HEADERS)
    html = r.text

    # Archidekt is Next.js — deck data lives in __NEXT_DATA__ JSON blob
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if match:
        try:
            next_data = json.loads(match.group(1))
            # Navigate props.pageProps structure
            page_props = next_data.get("props", {}).get("pageProps", {})
            folder = page_props.get("folder", {})
            decks = folder.get("decks", [])
            if decks:
                return [{"id": d["id"], "name": d["name"]} for d in decks]
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: regex scan for deck links in HTML
    deck_ids = re.findall(r'/decks/(\d+)[/"?]', html)
    names = re.findall(r'"name"\s*:\s*"([^"]+)"', html)

    seen = []
    result = []
    for i, did in enumerate(dict.fromkeys(deck_ids)):  # deduplicate, preserve order
        name = names[i] if i < len(names) else f"Deck {did}"
        result.append({"id": int(did), "name": name})
        seen.append(did)

    return result


async def sync_deck(deck_id: int) -> dict:
    """Fetch deck from Archidekt API and return {main_deck, sideboard}."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        r = await client.get(f"{API_BASE}/{deck_id}/", headers=HEADERS)

    if r.status_code != 200:
        return {"main_deck": [], "sideboard": []}

    data = r.json()
    main_deck: list[dict] = []
    sideboard: list[dict] = []

    for card_entry in data.get("cards", []):
        try:
            card_obj = card_entry.get("card", {})
            oracle = card_obj.get("oracleCard", {})
            name = oracle.get("name", "Unknown")
            qty = card_entry.get("quantity", 1)
            categories = [c.get("name", "") for c in card_entry.get("categories", [])]

            if "Sideboard" in categories:
                sideboard.append({"name": name, "quantity": qty})
            else:
                main_deck.append({"name": name, "quantity": qty})
        except (KeyError, TypeError):
            continue

    return {"main_deck": main_deck, "sideboard": sideboard}


async def sync_all_decks(existing_decks: list[dict]) -> list[dict]:
    """Sync all decks from the folder, preserving existing data."""
    folder_decks = await fetch_folder_deck_ids()
    existing_by_id = {d.get("archidekt_id"): d for d in existing_decks if d.get("archidekt_id")}

    result = []
    for fd in folder_decks:
        await asyncio.sleep(0.3)  # polite rate limiting
        cards = await sync_deck(fd["id"])
        existing = existing_by_id.get(fd["id"], {})
        from datetime import datetime, timezone
        entry = {
            **existing,
            "id": existing.get("id", f"archidekt-{fd['id']}"),
            "archidekt_id": fd["id"],
            "name": fd["name"],
            "archidekt_url": f"https://archidekt.com/decks/{fd['id']}",
            "last_synced": datetime.now(timezone.utc).isoformat(),
            **cards,
        }
        result.append(entry)

    return result
