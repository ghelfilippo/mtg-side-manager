from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from helpers import load, save
from services.archidekt import sync_all_decks, sync_deck

router = APIRouter()


@router.get("")
def get_my_decks():
    return load("my_decks.json")


@router.post("/sync")
async def sync_all():
    data = load("my_decks.json")
    existing = data.get("decks", [])
    synced = await sync_all_decks(existing)
    data["decks"] = synced
    data["last_folder_sync"] = datetime.now(timezone.utc).isoformat()
    save("my_decks.json", data)
    return data


@router.post("/{deck_id}/sync")
async def sync_single(deck_id: str):
    data = load("my_decks.json")
    deck = next((d for d in data.get("decks", []) if str(d.get("id")) == deck_id or str(d.get("archidekt_id")) == deck_id), None)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    archidekt_id = deck.get("archidekt_id")
    if not archidekt_id:
        raise HTTPException(status_code=400, detail="Deck has no Archidekt ID — sync all first")

    cards = await sync_deck(int(archidekt_id))
    deck.update({
        **cards,
        "last_synced": datetime.now(timezone.utc).isoformat(),
    })
    save("my_decks.json", data)
    return deck


@router.get("/{deck_id}/validate")
def validate_deck(deck_id: str):
    """Return list of sideboard plan entries that reference cards no longer in the main deck."""
    my_data = load("my_decks.json")
    deck = next(
        (d for d in my_data.get("decks", []) if str(d.get("id")) == deck_id),
        None,
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    main_names = {c["name"].lower() for c in deck.get("main_deck", [])}
    sb_data = load("sideboards.json")
    plans = sb_data.get("plans", {}).get(deck_id, {})

    stale = []
    for meta_id, plan in plans.items():
        for out_entry in plan.get("out", []):
            if out_entry["card"].lower() not in main_names:
                stale.append({"meta_deck_id": meta_id, "card": out_entry["card"]})

    return {"deck_id": deck_id, "stale": stale}
