# MTG Sideboard Manager

Webapp locale per gestire i sideboard Pauper dei tuoi mazzi Magic: The Gathering. Tutto gira in locale, nessun account, nessun cloud: file JSON come database.

![logo](https://img.shields.io/badge/MTG-Pauper-blueviolet) ![stack](https://img.shields.io/badge/stack-FastAPI%20%2B%20Alpine.js-informational)

## Cosa fa

- **Meta Deck** — Importa i mazzi del meta Pauper da **MTGGoldfish** con soglia di meta share configurabile. Categorizza (Aggro/Midrange/Control/Combo), includi/escludi, filtra per colori, ricerca per nome. Supporto **mazzi custom** (anche con link decklist personalizzato).
- **I Miei Mazzi** — Sincronizza da una folder **Archidekt**, mostra colori, link al deck e contatore side.
- **Editor Sideboard a due modalità**:
  - **Ufficiale**: la versione di produzione, quella che va in stampa.
  - **Teorica**: ramo parallelo per esperimenti — puoi aggiungere carte (validate via Scryfall), modificare le quantità in side, riorganizzare i piani; quando ti convince, **promuovi** in un click sulla ufficiale (solo se la side ha 15 carte). Puoi anche **resettare** la teorica dalla ufficiale corrente con un click.
- **Tabella editor stile Excel** — riga = carta, colonna = matchup. Header sticky (categorie + nomi mazzi + totali OUT/IN). Navigazione tra celle con frecce (↑↓←→) e Invio. Sezioni del mainboard tipizzate (Creature, Istantanei/Stregonerie, Altro, Terre). Riga Sideboard distinta in indaco.
- **Analisi sideboard** — per ogni mazzo, calcola in quanti matchup ogni carta è sidata IN/OUT. Le carte sidate IN molto spesso vengono segnalate come candidate al main deck.
- **Stampa compatta** — layout su 2 colonne, raggruppato per categoria (alfabetico dentro), pensato per stare in mezzo A4 / un A4 intero, leggibile durante un torneo.
- **Cleanup automatico** — quando re-sincronizzi un mazzo, le carte rimosse non vengono più contate nei piani (filtro orfani lato server). Piani per mazzi meta sparite vengono saltati nella stampa.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./start.sh
```

Browser su **http://localhost:8000**.

## Prima esecuzione

1. **I Miei Mazzi** → `📥 Importa side.xlsx` (se hai un Excel da migrare).
2. **Meta Deck** → `⟳ Aggiorna da MTGGoldfish` per caricare il meta.
3. **I Miei Mazzi** → `⟳ Sync da Archidekt` per i tuoi mazzi.
4. Apri un mazzo → **Editor Side** per pianificare i matchup.

## Struttura

```
main.py            # FastAPI app
helpers.py         # I/O JSON
routers/
  meta.py          # /api/meta — mazzi meta (MTGGoldfish + custom)
  my_decks.py      # /api/decks — mazzi propri (Archidekt sync)
  sideboards.py    # /api/sideboards — piani ufficiale/teorica + analisi + stampa
services/
  mtggoldfish.py   # scraper meta Pauper
  archidekt.py     # scraper folder + API singolo deck
  xlsx_import.py   # importer legacy
static/
  index.html       # frontend single-page (Alpine.js + Tailwind CDN)
data/              # JSON non committati
  meta_decks.json
  my_decks.json
  sideboards.json
```

## Modello dati sideboard

`sideboards.json` contiene **due rami paralleli** per ogni mazzo:

```jsonc
{
  "plans":                  { "<deck_id>": { "<meta_id>": {"in":[...], "out":[...], "notes":""} } },
  "theoretical_plans":      { "<deck_id>": { ... } },   // parallelo, indipendente
  "theoretical_sideboard":  { "<deck_id>": [...] },     // override sideboard in modalità teorica
  "theoretical_pool":       { ... }                     // legacy, ignorato dall'UI nuova
}
```

**Lazy-fork**: la prima volta che apri la modalità teorica per un mazzo, sideboard e piani sono uguali a ufficiale; iniziano a divergere solo quando salvi una modifica in teorica.

**Promote**: copia `theoretical_sideboard` → `deck.sideboard` (in `my_decks.json`) e `theoretical_plans` → `plans` (deep copy, restano indipendenti dopo). Richiede sideboard valida (15 carte).

**Reset**: copia `deck.sideboard` → `theoretical_sideboard` e `plans` → `theoretical_plans`, sovrascrivendo la teorica con lo stato ufficiale corrente.

## API

### Meta deck
| Metodo & Path | Note |
|---|---|
| `GET /api/meta/decks` | Lista |
| `POST /api/meta/fetch?min_share=0.2` | Aggiorna da MTGGoldfish |
| `PATCH /api/meta/decks/{id}` | category / included / name / image_url / arch_url (solo custom) |
| `POST /api/meta/decks/custom` | Crea mazzo custom (name, category, image_url, arch_url) |
| `DELETE /api/meta/decks/{id}` | Elimina (solo custom) |

### I miei mazzi
| Metodo & Path | Note |
|---|---|
| `GET /api/decks` | Lista |
| `POST /api/decks/sync` | Sync tutta la folder da Archidekt |
| `POST /api/decks/{id}/sync` | Sync mazzo singolo |

### Sideboard (ufficiale = default, teorica = `?mode=theoretical`)
| Metodo & Path | Note |
|---|---|
| `GET /api/sideboards/{deck_id}?mode=` | Piano + deck (side override in teorica). Piani orfani filtrati. |
| `PUT /api/sideboards/{deck_id}/{meta_id}?mode=` | Salva matchup (lazy-fork da ufficiale al primo write su teorica) |
| `DELETE /api/sideboards/{deck_id}/{meta_id}?mode=` | Rimuovi matchup |
| `POST /api/sideboards/{deck_id}/theoretical-side` | Upsert carta side teorica (qty=0 ⇒ rimuovi) |
| `DELETE /api/sideboards/{deck_id}/theoretical-side/{card_name}` | Rimuovi carta side teorica |
| `POST /api/sideboards/{deck_id}/promote-theoretical` | Promuovi teorica → ufficiale (richiede 15 carte) |
| `POST /api/sideboards/{deck_id}/reset-theoretical` | Resetta teorica ← ufficiale (sovrascrive sideboard + piani) |
| `GET /api/sideboards/{deck_id}/analysis?mode=` | Aggregazione carte sidate IN/OUT per matchup |
| `GET /api/sideboards/{deck_id}/print` | Dati stampa (sempre ufficiale) |

### Misc
| Metodo & Path | Note |
|---|---|
| `POST /api/import/xlsx` | Importa side.xlsx (legacy) |

## Stack

- **Backend**: FastAPI (Python 3.10+), `uvicorn`, `httpx` + `beautifulsoup4` per scraping, `openpyxl` per xlsx legacy.
- **Frontend**: HTML singolo + **Alpine.js 3** (CDN) + **Tailwind CSS** JIT (CDN). Validazione nomi carta via **Scryfall**.
- **Persistenza**: file JSON in `data/` (non committati). Per backup, basta zippare la cartella.
- **Hostable**: gira in locale, ma stateless rispetto a sessioni, quindi serviable anche da una VPS dietro un reverse proxy.
