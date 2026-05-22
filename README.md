# MTG Sideboard Manager

Webapp locale per gestire il sideboard pauper dei tuoi mazzi Magic: The Gathering.

## Funzionalità

- **Meta Deck Manager** — Sincronizza i mazzi del meta Pauper da MTGTOP8, assegna categorie (Aggro/Midrange/Control/Combo), includi/escludi, vedi top decklist
- **I Miei Mazzi** — Sync automatico da Archidekt (folder dedicata), rilevamento side invalide (carte rimosse dal mazzo)
- **Editor Sideboard** — Tabella Excel-like per pianificare IN/OUT per ogni matchup, supporto carte teoriche oltre le 15
- **Stampa** — Export compatto per il portamazzo, layout 2 colonne ottimizzato per stampa

## Setup

```bash
# Crea e attiva venv
python3 -m venv .venv
source .venv/bin/activate

# Installa dipendenze
pip install -r requirements.txt

# Avvia
./start.sh
```

Apri il browser su **http://localhost:8000**

## Prima esecuzione

1. Vai su **I Miei Mazzi** → clicca **📥 Importa side.xlsx** per importare i dati dall'Excel
2. Vai su **Meta Deck** → clicca **⟳ Aggiorna da MTGTOP8** per caricare il meta corrente
3. Vai su **I Miei Mazzi** → clicca **⟳ Sync da Archidekt** per caricare i mazzi aggiornati

## Struttura

```
main.py           # FastAPI app
helpers.py        # I/O su file JSON
routers/          # API routes (meta, my_decks, sideboards)
services/         # Scraping (mtgtop8, archidekt) + import xlsx
static/           # Frontend (Alpine.js + Tailwind, single HTML)
data/             # Database JSON (non committato)
  meta_decks.json
  my_decks.json
  sideboards.json
```

## API

| Endpoint | Descrizione |
|---|---|
| `POST /api/import/xlsx` | Importa side.xlsx |
| `GET /api/meta/decks` | Lista mazzi meta |
| `POST /api/meta/fetch` | Aggiorna da MTGTOP8 |
| `PATCH /api/meta/decks/{id}` | Modifica categoria/includi |
| `GET /api/meta/decks/{id}/preview` | Top decklist |
| `GET /api/decks` | I miei mazzi |
| `POST /api/decks/sync` | Sync tutti da Archidekt |
| `POST /api/decks/{id}/sync` | Sync mazzo singolo |
| `GET /api/sideboards/{deck_id}` | Piano sideboard |
| `PUT /api/sideboards/{deck_id}/{meta_id}` | Salva matchup |
| `GET /api/sideboards/{deck_id}/print` | Dati per stampa |
