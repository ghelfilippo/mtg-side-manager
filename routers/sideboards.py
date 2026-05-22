from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from helpers import load, save

router = APIRouter()


class CardEntry(BaseModel):
    card: str
    quantity: int


class MatchupPlan(BaseModel):
    out: list[CardEntry] = []
    in_: list[CardEntry] = []
    notes: str = ""

    model_config = {"populate_by_name": True}

    def to_dict(self):
        return {"out": [e.model_dump() for e in self.out], "in": [e.model_dump() for e in self.in_], "notes": self.notes}


class TheoreticalCard(BaseModel):
    card: str
    quantity: int


@router.get("/{deck_id}")
def get_sideboard_plan(deck_id: str):
    sb_data = load("sideboards.json")
    my_data = load("my_decks.json")

    deck = next((d for d in my_data.get("decks", []) if str(d.get("id")) == deck_id), None)
    main_names = {c["name"].lower() for c in (deck or {}).get("main_deck", [])} if deck else set()

    plans = sb_data.get("plans", {}).get(deck_id, {})
    theoretical = sb_data.get("theoretical_pool", {}).get(deck_id, [])

    # Annotate stale OUT entries
    annotated_plans = {}
    for meta_id, plan in plans.items():
        annotated_out = []
        for entry in plan.get("out", []):
            annotated_out.append({**entry, "stale": entry["card"].lower() not in main_names})
        annotated_plans[meta_id] = {**plan, "out": annotated_out}

    return {
        "deck_id": deck_id,
        "plans": annotated_plans,
        "theoretical_pool": theoretical,
        "deck": deck,
    }


@router.put("/{deck_id}/{meta_deck_id:path}")
def set_matchup_plan(deck_id: str, meta_deck_id: str, body: dict):
    sb_data = load("sideboards.json")
    if deck_id not in sb_data["plans"]:
        sb_data["plans"][deck_id] = {}
    sb_data["plans"][deck_id][meta_deck_id] = body
    save("sideboards.json", sb_data)
    return sb_data["plans"][deck_id][meta_deck_id]


@router.delete("/{deck_id}/{meta_deck_id:path}")
def delete_matchup_plan(deck_id: str, meta_deck_id: str):
    sb_data = load("sideboards.json")
    plans = sb_data.get("plans", {}).get(deck_id, {})
    if meta_deck_id in plans:
        del plans[meta_deck_id]
        save("sideboards.json", sb_data)
    return {"deleted": True}


@router.get("/{deck_id}/theoretical")
def get_theoretical_pool(deck_id: str):
    sb_data = load("sideboards.json")
    return sb_data.get("theoretical_pool", {}).get(deck_id, [])


@router.post("/{deck_id}/theoretical")
def add_theoretical_card(deck_id: str, card: TheoreticalCard):
    sb_data = load("sideboards.json")
    pool = sb_data.setdefault("theoretical_pool", {}).setdefault(deck_id, [])
    # Update if exists, else append
    existing = next((c for c in pool if c["card"].lower() == card.card.lower()), None)
    if existing:
        existing["quantity"] = card.quantity
    else:
        pool.append({"card": card.card, "quantity": card.quantity, "theoretical": True})
    save("sideboards.json", sb_data)
    return pool


@router.delete("/{deck_id}/theoretical/{card_name}")
def remove_theoretical_card(deck_id: str, card_name: str):
    sb_data = load("sideboards.json")
    pool = sb_data.get("theoretical_pool", {}).get(deck_id, [])
    sb_data["theoretical_pool"][deck_id] = [
        c for c in pool if c["card"].lower() != card_name.lower()
    ]
    save("sideboards.json", sb_data)
    return {"deleted": True}


@router.get("/{deck_id}/print")
def get_print_data(deck_id: str):
    sb_data = load("sideboards.json")
    meta_data = load("meta_decks.json")
    meta_by_id = {d["id"]: d for d in meta_data.get("decks", [])}
    plans = sb_data.get("plans", {}).get(deck_id, {})
    my_data = load("my_decks.json")
    deck = next((d for d in my_data.get("decks", []) if str(d.get("id")) == deck_id), None)

    result = []
    for meta_id, plan in plans.items():
        meta_deck = meta_by_id.get(meta_id, {"name": meta_id, "category": "Unknown", "included": True})
        if not meta_deck.get("included", True):
            continue
        ins = plan.get("in", [])
        outs = plan.get("out", [])
        if not ins and not outs:
            continue
        result.append({
            "matchup": meta_deck.get("name", meta_id),
            "category": meta_deck.get("category", "Unknown"),
            "in": ins,
            "out": outs,
            "notes": plan.get("notes", ""),
        })

    cat_order = {"Aggro": 0, "Midrange": 1, "Control": 2, "Combo": 3}
    result.sort(key=lambda x: (cat_order.get(x["category"], 9), x["matchup"].lower()))

    return {"deck_id": deck_id, "deck_name": deck["name"] if deck else deck_id, "matchups": result}
