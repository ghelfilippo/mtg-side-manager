from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from helpers import load, save
from services.mtgtop8 import fetch_meta, fetch_top_decklist

router = APIRouter()


class MetaDeckUpdate(BaseModel):
    category: Optional[str] = None
    included: Optional[bool] = None


@router.get("/decks")
def get_meta_decks():
    return load("meta_decks.json")


@router.post("/fetch")
async def fetch_meta_decks():
    existing = load("meta_decks.json")
    user_overrides = {
        d["id"]: {"category": d.get("category"), "included": d.get("included", True)}
        for d in existing.get("decks", [])
    }

    fresh = await fetch_meta()

    for deck in fresh.get("decks", []):
        if deck["id"] in user_overrides:
            overrides = user_overrides[deck["id"]]
            if overrides.get("category") is not None:
                deck["category"] = overrides["category"]
            deck["included"] = overrides.get("included", True)

    fresh["last_fetched"] = datetime.now(timezone.utc).isoformat()

    # Preserve top_decklist_url and meta_id from existing entries
    existing_by_id = {d["id"]: d for d in existing.get("decks", [])}
    for deck in fresh.get("decks", []):
        if deck["id"] in existing_by_id:
            existing_entry = existing_by_id[deck["id"]]
            if not deck.get("top_decklist_url") and existing_entry.get("top_decklist_url"):
                deck["top_decklist_url"] = existing_entry["top_decklist_url"]

    save("meta_decks.json", fresh)
    return fresh


@router.patch("/decks/{deck_id:path}")
def update_meta_deck(deck_id: str, update: MetaDeckUpdate):
    data = load("meta_decks.json")
    for deck in data.get("decks", []):
        if deck["id"] == deck_id:
            if update.category is not None:
                deck["category"] = update.category
            if update.included is not None:
                deck["included"] = update.included
            save("meta_decks.json", data)
            return deck
    raise HTTPException(status_code=404, detail="Deck not found")


@router.get("/decks/{deck_id:path}/preview")
async def preview_decklist(deck_id: str):
    data = load("meta_decks.json")
    deck = next((d for d in data.get("decks", []) if d["id"] == deck_id), None)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    arch_id = deck.get("archetype_id")
    meta_id = deck.get("meta_id") or data.get("meta_id")

    if not arch_id:
        raise HTTPException(status_code=400, detail="No archetype_id (imported deck)")

    result = await fetch_top_decklist(arch_id, meta_id)

    # Cache the source URL
    if result.get("source_url") and not deck.get("top_decklist_url"):
        deck["top_decklist_url"] = result["source_url"]
        save("meta_decks.json", data)

    return result
