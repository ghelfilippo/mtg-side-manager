import json
import pathlib

DATA = pathlib.Path("data")


def _path(filename: str, user_id: str | None = None) -> pathlib.Path:
    if user_id:
        d = DATA / user_id
        d.mkdir(parents=True, exist_ok=True)
        return d / filename
    return DATA / filename


def load(filename: str, user_id: str | None = None) -> dict:
    p = _path(filename, user_id)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def save(filename: str, data: dict, user_id: str | None = None) -> None:
    p = _path(filename, user_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
