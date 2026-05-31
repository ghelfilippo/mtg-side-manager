from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from helpers import load, save
from services.archidekt import sync_all_decks, sync_deck

router = APIRouter()


@router.get("")
def get_my_decks(user: dict = Depends(get_current_user)):
    return load("my_decks.json", user["username"])


@router.post("/sync")
async def sync_all(user: dict = Depends(get_current_user)):
    uid = user["username"]
    folder_id = user.get("archidekt_folder_id", "")
    if not folder_id:
        raise HTTPException(status_code=400,
                            detail="No Archidekt folder configured. Set it in the Admin panel.")
    data = load("my_decks.json", uid)
    existing = data.get("decks", [])
    synced = await sync_all_decks(existing, folder_id)
    data["decks"] = synced
    data["last_folder_sync"] = datetime.now(timezone.utc).isoformat()
    save("my_decks.json", data, uid)
    return data


@router.post("/{deck_id}/sync")
async def sync_single(deck_id: str, user: dict = Depends(get_current_user)):
    uid = user["username"]
    data = load("my_decks.json", uid)
    deck = next(
        (d for d in data.get("decks", [])
         if str(d.get("id")) == deck_id or str(d.get("archidekt_id")) == deck_id),
        None,
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    archidekt_id = deck.get("archidekt_id")
    if not archidekt_id:
        raise HTTPException(status_code=400,
                            detail="Deck has no Archidekt ID — sync all first")
    cards = await sync_deck(int(archidekt_id))
    deck.update({**cards, "last_synced": datetime.now(timezone.utc).isoformat()})
    save("my_decks.json", data, uid)
    return deck


@router.get("/{deck_id}/validate")
def validate_deck(deck_id: str, user: dict = Depends(get_current_user)):
    """Return stale OUT entries (cards no longer in the main deck) and clean them up."""
    uid = user["username"]
    my_data = load("my_decks.json", uid)
    deck = next(
        (d for d in my_data.get("decks", []) if str(d.get("id")) == deck_id),
        None,
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    main_names = {c["name"].lower() for c in deck.get("main_deck", [])}
    sb_data = load("sideboards.json", uid)
    plans = sb_data.get("plans", {}).get(deck_id, {})

    stale = []
    changed = False
    for meta_id, plan in plans.items():
        clean_out = [e for e in plan.get("out", []) if e["card"].lower() in main_names]
        removed = [e for e in plan.get("out", []) if e["card"].lower() not in main_names]
        if removed:
            stale.extend({"meta_deck_id": meta_id, "card": e["card"]} for e in removed)
            plan["out"] = clean_out
            changed = True

    if changed:
        save("sideboards.json", sb_data, uid)

    return {"deck_id": deck_id, "stale": stale}
