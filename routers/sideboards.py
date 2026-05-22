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


def _valid_names(deck, theoretical):
    """Lowercased name sets: (main deck cards, valid IN cards = sideboard + theoretical)."""
    main = {c["name"].lower() for c in (deck or {}).get("main_deck", [])}
    side = {c["name"].lower() for c in (deck or {}).get("sideboard", [])}
    theo = {t.get("card", "").lower() for t in (theoretical or [])}
    return main, side | theo


def _clean_plan(plan, main_names, valid_in):
    """Drop OUT/IN entries for cards no longer in the deck (orphaned after a re-sync)."""
    return {
        **plan,
        "out": [e for e in plan.get("out", []) if e.get("card", "").lower() in main_names],
        "in": [e for e in plan.get("in", []) if e.get("card", "").lower() in valid_in],
    }


@router.get("/{deck_id}")
def get_sideboard_plan(deck_id: str):
    sb_data = load("sideboards.json")
    my_data = load("my_decks.json")

    deck = next((d for d in my_data.get("decks", []) if str(d.get("id")) == deck_id), None)
    theoretical = sb_data.get("theoretical_pool", {}).get(deck_id, [])
    main_names, valid_in = _valid_names(deck, theoretical)

    plans = sb_data.get("plans", {}).get(deck_id, {})
    cleaned = {mid: _clean_plan(p, main_names, valid_in) for mid, p in plans.items()}

    return {
        "deck_id": deck_id,
        "plans": cleaned,
        "theoretical_pool": theoretical,
        "deck": deck,
    }


@router.get("/{deck_id}/theoretical")
def get_theoretical_pool(deck_id: str):
    sb_data = load("sideboards.json")
    return sb_data.get("theoretical_pool", {}).get(deck_id, [])


@router.post("/{deck_id}/theoretical")
def add_theoretical_card(deck_id: str, card: TheoreticalCard):
    sb_data = load("sideboards.json")
    pool = sb_data.setdefault("theoretical_pool", {}).setdefault(deck_id, [])
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


@router.get("/{deck_id}/print")
def get_print_data(deck_id: str):
    sb_data = load("sideboards.json")
    meta_data = load("meta_decks.json")
    meta_by_id = {d["id"]: d for d in meta_data.get("decks", [])}
    plans = sb_data.get("plans", {}).get(deck_id, {})
    my_data = load("my_decks.json")
    deck = next((d for d in my_data.get("decks", []) if str(d.get("id")) == deck_id), None)
    theoretical = sb_data.get("theoretical_pool", {}).get(deck_id, [])
    main_names, valid_in = _valid_names(deck, theoretical)

    result = []
    for meta_id, plan in plans.items():
        meta_deck = meta_by_id.get(meta_id)
        if not meta_deck:
            continue  # stale plan — meta deck no longer exists
        if not meta_deck.get("included", True):
            continue
        plan = _clean_plan(plan, main_names, valid_in)
        ins = plan["in"]
        outs = plan["out"]
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


@router.get("/{deck_id}/analysis")
def get_sideboard_analysis(deck_id: str):
    """Aggregate all matchup plans: how often each card is sided in / out."""
    sb_data = load("sideboards.json")
    meta_data = load("meta_decks.json")
    meta_by_id = {d["id"]: d for d in meta_data.get("decks", [])}
    plans = sb_data.get("plans", {}).get(deck_id, {})
    my_data = load("my_decks.json")
    deck = next((d for d in my_data.get("decks", []) if str(d.get("id")) == deck_id), None)
    theoretical = sb_data.get("theoretical_pool", {}).get(deck_id, [])
    main_names, valid_in = _valid_names(deck, theoretical)

    in_counter: dict = {}
    out_counter: dict = {}
    total = 0

    for meta_id, plan in plans.items():
        meta_deck = meta_by_id.get(meta_id)
        if not meta_deck or not meta_deck.get("included", True):
            continue
        plan = _clean_plan(plan, main_names, valid_in)
        ins = plan["in"]
        outs = plan["out"]
        if not ins and not outs:
            continue
        total += 1
        for e in ins:
            entry = in_counter.setdefault(e["card"], {"card": e["card"], "count": 0, "qty": 0})
            entry["count"] += 1
            entry["qty"] += e.get("quantity", 0)
        for e in outs:
            entry = out_counter.setdefault(e["card"], {"card": e["card"], "count": 0, "qty": 0})
            entry["count"] += 1
            entry["qty"] += e.get("quantity", 0)

    def finalize(counter: dict) -> list:
        items = list(counter.values())
        for it in items:
            it["pct"] = round(it["count"] / total * 100) if total else 0
        items.sort(key=lambda x: (-x["count"], -x["qty"], x["card"].lower()))
        return items

    return {
        "deck_id": deck_id,
        "total_matchups": total,
        "most_in": finalize(in_counter),
        "most_out": finalize(out_counter),
    }
