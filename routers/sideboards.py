import copy
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from helpers import load, save

router = APIRouter()


class CardEntry(BaseModel):
    card: str
    quantity: int


class TheoreticalCard(BaseModel):
    card: str
    quantity: int


class TheoSideCard(BaseModel):
    card: str
    quantity: int


# ---------- helpers ----------

def _valid_names(deck, theoretical):
    main = {c["name"].lower() for c in (deck or {}).get("main_deck", [])}
    side = {c["name"].lower() for c in (deck or {}).get("sideboard", [])}
    theo = {t.get("card", "").lower() for t in (theoretical or [])}
    return main, side | theo


def _clean_plan(plan, main_names, valid_in):
    return {
        **plan,
        "out": [e for e in plan.get("out", []) if e.get("card", "").lower() in main_names],
        "in": [e for e in plan.get("in", []) if e.get("card", "").lower() in valid_in],
    }


def _theoretical_sideboard(sb_data: dict, deck: Optional[dict], deck_id: str) -> list:
    overrides = sb_data.get("theoretical_sideboard", {})
    if deck_id in overrides:
        return list(overrides[deck_id])
    base = [dict(c) for c in (deck or {}).get("sideboard", [])]
    legacy = sb_data.get("theoretical_pool", {}).get(deck_id, [])
    seen = {c["name"].lower() for c in base}
    for t in legacy:
        name = t.get("card", "")
        if name and name.lower() not in seen:
            base.append({"name": name, "quantity": t.get("quantity", 1), "types": []})
            seen.add(name.lower())
    return base


def _plans_for_mode(sb_data: dict, deck_id: str, mode: str) -> dict:
    if mode == "theoretical":
        theo_all = sb_data.get("theoretical_plans", {})
        if deck_id in theo_all:
            return theo_all[deck_id]
    return sb_data.get("plans", {}).get(deck_id, {})


def _plans_collection_rw(sb_data: dict, mode: str) -> dict:
    if mode == "theoretical":
        return sb_data.setdefault("theoretical_plans", {})
    return sb_data.setdefault("plans", {})


# ---------- main GET ----------

@router.get("/{deck_id}")
def get_sideboard_plan(deck_id: str, mode: str = "official",
                       user: dict = Depends(get_current_user)):
    uid = user["username"]
    sb_data = load("sideboards.json", uid)
    my_data = load("my_decks.json", uid)

    deck = next((d for d in my_data.get("decks", []) if str(d.get("id")) == deck_id), None)

    if mode == "theoretical":
        side = _theoretical_sideboard(sb_data, deck, deck_id)
        if deck is not None:
            deck = {**deck, "sideboard": side}
        legacy_theo = []
    else:
        legacy_theo = sb_data.get("theoretical_pool", {}).get(deck_id, [])

    plans = _plans_for_mode(sb_data, deck_id, mode)
    main_names, valid_in = _valid_names(deck, legacy_theo)
    cleaned = {mid: _clean_plan(p, main_names, valid_in) for mid, p in plans.items()}

    if cleaned != plans:
        _plans_collection_rw(sb_data, mode).setdefault(deck_id, {}).update(cleaned)
        coll = _plans_collection_rw(sb_data, mode).get(deck_id, {})
        for mid in list(coll.keys()):
            if mid not in cleaned:
                del coll[mid]
        save("sideboards.json", sb_data, uid)

    return {
        "deck_id": deck_id,
        "mode": mode,
        "plans": cleaned,
        "theoretical_pool": sb_data.get("theoretical_pool", {}).get(deck_id, []),
        "deck": deck,
    }


# ---------- legacy theoretical_pool ----------

@router.get("/{deck_id}/theoretical")
def get_theoretical_pool(deck_id: str, user: dict = Depends(get_current_user)):
    uid = user["username"]
    sb_data = load("sideboards.json", uid)
    return sb_data.get("theoretical_pool", {}).get(deck_id, [])


@router.post("/{deck_id}/theoretical")
def add_theoretical_card(deck_id: str, card: TheoreticalCard,
                         user: dict = Depends(get_current_user)):
    uid = user["username"]
    sb_data = load("sideboards.json", uid)
    pool = sb_data.setdefault("theoretical_pool", {}).setdefault(deck_id, [])
    existing = next((c for c in pool if c["card"].lower() == card.card.lower()), None)
    if existing:
        existing["quantity"] = card.quantity
    else:
        pool.append({"card": card.card, "quantity": card.quantity, "theoretical": True})
    save("sideboards.json", sb_data, uid)
    return pool


@router.delete("/{deck_id}/theoretical/{card_name}")
def remove_theoretical_card(deck_id: str, card_name: str,
                             user: dict = Depends(get_current_user)):
    uid = user["username"]
    sb_data = load("sideboards.json", uid)
    pool = sb_data.get("theoretical_pool", {}).get(deck_id, [])
    sb_data["theoretical_pool"][deck_id] = [
        c for c in pool if c["card"].lower() != card_name.lower()
    ]
    save("sideboards.json", sb_data, uid)
    return {"deleted": True}


# ---------- theoretical mode sideboard ----------

@router.post("/{deck_id}/theoretical-side")
def upsert_theoretical_side(deck_id: str, body: TheoSideCard,
                             user: dict = Depends(get_current_user)):
    uid = user["username"]
    sb_data = load("sideboards.json", uid)
    my_data = load("my_decks.json", uid)
    deck = next((d for d in my_data.get("decks", []) if str(d.get("id")) == deck_id), None)
    side = _theoretical_sideboard(sb_data, deck, deck_id)

    name_l = body.card.lower()
    existing = next((c for c in side if c["name"].lower() == name_l), None)
    if body.quantity <= 0:
        if existing:
            side.remove(existing)
    elif existing:
        existing["quantity"] = body.quantity
    else:
        side.append({"name": body.card, "quantity": body.quantity, "types": []})

    sb_data.setdefault("theoretical_sideboard", {})[deck_id] = side
    save("sideboards.json", sb_data, uid)
    return {"sideboard": side}


@router.delete("/{deck_id}/theoretical-side/{card_name:path}")
def remove_theoretical_side(deck_id: str, card_name: str,
                             user: dict = Depends(get_current_user)):
    uid = user["username"]
    sb_data = load("sideboards.json", uid)
    my_data = load("my_decks.json", uid)
    deck = next((d for d in my_data.get("decks", []) if str(d.get("id")) == deck_id), None)
    side = _theoretical_sideboard(sb_data, deck, deck_id)
    side = [c for c in side if c["name"].lower() != card_name.lower()]
    sb_data.setdefault("theoretical_sideboard", {})[deck_id] = side
    save("sideboards.json", sb_data, uid)
    return {"sideboard": side}


@router.post("/{deck_id}/promote-theoretical")
def promote_theoretical_sideboard(deck_id: str, user: dict = Depends(get_current_user)):
    uid = user["username"]
    sb_data = load("sideboards.json", uid)
    my_data = load("my_decks.json", uid)
    deck_idx = next(
        (i for i, d in enumerate(my_data.get("decks", [])) if str(d.get("id")) == deck_id),
        None,
    )
    if deck_idx is None:
        raise HTTPException(status_code=404, detail="Deck not found")
    deck = my_data["decks"][deck_idx]
    side = _theoretical_sideboard(sb_data, deck, deck_id)
    total = sum(c.get("quantity", 0) for c in side)
    if total != 15:
        raise HTTPException(status_code=400,
                            detail=f"Theoretical sideboard has {total} cards (exactly 15 required)")

    new_side = [
        {"name": c["name"], "quantity": c["quantity"], "types": c.get("types", [])}
        for c in side
    ]
    my_data["decks"][deck_idx]["sideboard"] = new_side
    save("my_decks.json", my_data, uid)

    theo_plans = sb_data.get("theoretical_plans", {}).get(deck_id)
    plans_promoted = 0
    if theo_plans:
        sb_data.setdefault("plans", {})[deck_id] = copy.deepcopy(theo_plans)
        plans_promoted = len(theo_plans)
        save("sideboards.json", sb_data, uid)

    return {"promoted": True, "sideboard": new_side, "total": total,
            "plans_promoted": plans_promoted}


@router.post("/{deck_id}/reset-theoretical")
def reset_theoretical_from_official(deck_id: str, user: dict = Depends(get_current_user)):
    uid = user["username"]
    sb_data = load("sideboards.json", uid)
    my_data = load("my_decks.json", uid)
    deck = next((d for d in my_data.get("decks", []) if str(d.get("id")) == deck_id), None)
    if deck is None:
        raise HTTPException(status_code=404, detail="Deck not found")

    official_side = [
        {"name": c["name"], "quantity": c["quantity"], "types": c.get("types", [])}
        for c in deck.get("sideboard", [])
    ]
    official_plans = sb_data.get("plans", {}).get(deck_id, {})

    sb_data.setdefault("theoretical_sideboard", {})[deck_id] = official_side
    sb_data.setdefault("theoretical_plans", {})[deck_id] = copy.deepcopy(official_plans)
    save("sideboards.json", sb_data, uid)

    return {
        "reset": True,
        "total": sum(c["quantity"] for c in official_side),
        "plans_copied": len(official_plans),
    }


# ---------- plans PUT/DELETE ----------

@router.put("/{deck_id}/{meta_deck_id:path}")
def set_matchup_plan(deck_id: str, meta_deck_id: str, body: dict,
                     mode: str = "official", user: dict = Depends(get_current_user)):
    uid = user["username"]
    sb_data = load("sideboards.json", uid)
    coll = _plans_collection_rw(sb_data, mode)
    if deck_id not in coll:
        if mode == "theoretical":
            coll[deck_id] = {k: dict(v) for k, v in
                             sb_data.get("plans", {}).get(deck_id, {}).items()}
        else:
            coll[deck_id] = {}
    coll[deck_id][meta_deck_id] = body
    save("sideboards.json", sb_data, uid)
    return coll[deck_id][meta_deck_id]


@router.delete("/{deck_id}/{meta_deck_id:path}")
def delete_matchup_plan(deck_id: str, meta_deck_id: str,
                        mode: str = "official", user: dict = Depends(get_current_user)):
    uid = user["username"]
    sb_data = load("sideboards.json", uid)
    coll = _plans_collection_rw(sb_data, mode)
    plans = coll.get(deck_id, {})
    if meta_deck_id in plans:
        del plans[meta_deck_id]
        save("sideboards.json", sb_data, uid)
    return {"deleted": True}


# ---------- print ----------

@router.get("/{deck_id}/print")
def get_print_data(deck_id: str, user: dict = Depends(get_current_user)):
    uid = user["username"]
    sb_data = load("sideboards.json", uid)
    meta_data = load("meta_decks.json", uid)
    meta_by_id = {d["id"]: d for d in meta_data.get("decks", [])}
    plans = sb_data.get("plans", {}).get(deck_id, {})
    my_data = load("my_decks.json", uid)
    deck = next((d for d in my_data.get("decks", []) if str(d.get("id")) == deck_id), None)
    theoretical = sb_data.get("theoretical_pool", {}).get(deck_id, [])
    main_names, valid_in = _valid_names(deck, theoretical)

    result = []
    for meta_id, plan in plans.items():
        meta_deck = meta_by_id.get(meta_id)
        if not meta_deck or not meta_deck.get("included", True):
            continue
        plan = _clean_plan(plan, main_names, valid_in)
        ins, outs = plan["in"], plan["out"]
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
    return {"deck_id": deck_id,
            "deck_name": deck["name"] if deck else deck_id,
            "matchups": result}


# ---------- analysis ----------

@router.get("/{deck_id}/analysis")
def get_sideboard_analysis(deck_id: str, mode: str = "official",
                           user: dict = Depends(get_current_user)):
    uid = user["username"]
    sb_data = load("sideboards.json", uid)
    meta_data = load("meta_decks.json", uid)
    meta_by_id = {d["id"]: d for d in meta_data.get("decks", [])}
    my_data = load("my_decks.json", uid)
    deck = next((d for d in my_data.get("decks", []) if str(d.get("id")) == deck_id), None)

    if mode == "theoretical":
        side = _theoretical_sideboard(sb_data, deck, deck_id)
        if deck is not None:
            deck = {**deck, "sideboard": side}
        legacy_theo = []
    else:
        legacy_theo = sb_data.get("theoretical_pool", {}).get(deck_id, [])

    plans = _plans_for_mode(sb_data, deck_id, mode)
    main_names, valid_in = _valid_names(deck, legacy_theo)

    in_counter: dict = {}
    out_counter: dict = {}
    total = 0

    for meta_id, plan in plans.items():
        meta_deck = meta_by_id.get(meta_id)
        if not meta_deck or not meta_deck.get("included", True):
            continue
        plan = _clean_plan(plan, main_names, valid_in)
        ins, outs = plan["in"], plan["out"]
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
        "mode": mode,
        "total_matchups": total,
        "most_in": finalize(in_counter),
        "most_out": finalize(out_counter),
    }
