from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from routers import meta, my_decks, sideboards

app = FastAPI(title="MTG Sideboard Manager")

app.include_router(meta.router, prefix="/api/meta", tags=["meta"])
app.include_router(my_decks.router, prefix="/api/decks", tags=["decks"])
app.include_router(sideboards.router, prefix="/api/sideboards", tags=["sideboards"])


@app.post("/api/import/xlsx")
async def import_xlsx(path: str = "side.xlsx"):
    from services.xlsx_import import import_from_xlsx
    return import_from_xlsx(path)


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root():
    return FileResponse("static/index.html")
