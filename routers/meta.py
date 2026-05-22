from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from helpers import load, save
from services.mtggoldfish import fetch_meta as fetch_meta_goldfish

router = APIRouter()


class MetaDeckUpdate(BaseModel):
    category: Optional[str] = None
    included: Optional[bool] = None
    name: Optional[str] = None


class CustomDeck(BaseModel):
    name: str
    category: str = "Aggro"


@router.get("/decks")
def get_meta_decks():
    return load("meta_decks.json")


@router.post("/fetch")
async def fetch_meta_decks(min_share: float = 0.2):
    existing = load("meta_decks.json")
    user_overrides = {
        d["id"]: {
            "category": d.get("category"),
            "included": d.get("included", True),
        }
        for d in existing.get("decks", [])
    }

    fresh = await fetch_meta_goldfish(min_share=min_share)
    if "error" in fresh:
        raise HTTPException(status_code=502, detail=fresh["error"])

    # Preserve user overrides; keep custom decks untouched
    custom_decks = [d for d in existing.get("decks", []) if d.get("source") == "custom"]
    for deck in fresh.get("decks", []):
        if deck["id"] in user_overrides:
            ov = user_overrides[deck["id"]]
            if ov.get("category") is not None:
                deck["category"] = ov["category"]
            deck["included"] = ov.get("included", True)

    result = {
        "last_fetched": datetime.now(timezone.utc).isoformat(),
        "source_url": fresh.get("source_url", ""),
        "decks": fresh.get("decks", []) + custom_decks,
    }
    save("meta_decks.json", result)
    return result


@router.patch("/decks/{deck_id:path}")
def update_meta_deck(deck_id: str, update: MetaDeckUpdate):
    data = load("meta_decks.json")
    for deck in data.get("decks", []):
        if deck["id"] == deck_id:
            if update.category is not None:
                deck["category"] = update.category
            if update.included is not None:
                deck["included"] = update.included
            if update.name is not None and deck.get("source") == "custom":
                deck["name"] = update.name
            save("meta_decks.json", data)
            return deck
    raise HTTPException(status_code=404, detail="Deck not found")


@router.post("/decks/custom")
def add_custom_deck(body: CustomDeck):
    import re
    data = load("meta_decks.json")
    deck_id = f"custom-{re.sub(r'[^a-z0-9]+', '-', body.name.lower()).strip('-')}"
    if any(d["id"] == deck_id for d in data.get("decks", [])):
        raise HTTPException(status_code=409, detail="Deck with this name already exists")
    new_deck = {
        "id": deck_id,
        "name": body.name,
        "category": body.category,
        "meta_share": 0.0,
        "image_url": "",
        "arch_url": "",
        "colors": [],
        "included": True,
        "source": "custom",
    }
    data.setdefault("decks", []).append(new_deck)
    save("meta_decks.json", data)
    return new_deck


@router.delete("/decks/{deck_id:path}")
def delete_meta_deck(deck_id: str):
    data = load("meta_decks.json")
    deck = next((d for d in data.get("decks", []) if d["id"] == deck_id), None)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    if deck.get("source") != "custom":
        raise HTTPException(status_code=400, detail="Only custom decks can be deleted")
    data["decks"] = [d for d in data["decks"] if d["id"] != deck_id]
    save("meta_decks.json", data)
    return {"deleted": True}
