import json
import pathlib

DATA = pathlib.Path("data")


def load(filename: str) -> dict:
    p = DATA / filename
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save(filename: str, data: dict) -> None:
    DATA.mkdir(exist_ok=True)
    (DATA / filename).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
