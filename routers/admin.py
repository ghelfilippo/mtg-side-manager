from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from auth import get_current_user, hash_password, load_users, require_admin, save_users

router = APIRouter()


class UserCreate(BaseModel):
    username: str
    password: str
    archidekt_folder_id: str = ""
    is_admin: bool = False


class UserUpdate(BaseModel):
    password: Optional[str] = None
    archidekt_folder_id: Optional[str] = None
    is_admin: Optional[bool] = None


@router.get("/users")
def list_users(_: dict = Depends(require_admin)):
    return [
        {
            "username": u["username"],
            "archidekt_folder_id": u.get("archidekt_folder_id", ""),
            "is_admin": u.get("is_admin", False),
        }
        for u in load_users()
    ]


@router.post("/users", status_code=201)
def create_user(body: UserCreate, _: dict = Depends(require_admin)):
    users = load_users()
    if any(u["username"] == body.username for u in users):
        raise HTTPException(status_code=409, detail="Username already taken")
    users.append({
        "username": body.username,
        "password_hash": hash_password(body.password),
        "archidekt_folder_id": body.archidekt_folder_id,
        "is_admin": body.is_admin,
    })
    save_users(users)
    return {"created": True, "username": body.username}


@router.patch("/users/{username}")
def update_user(username: str, body: UserUpdate,
                current: dict = Depends(require_admin)):
    users = load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.password is not None:
        user["password_hash"] = hash_password(body.password)
    if body.archidekt_folder_id is not None:
        user["archidekt_folder_id"] = body.archidekt_folder_id
    if body.is_admin is not None:
        # Prevent removing your own admin rights
        if username == current["username"] and not body.is_admin:
            raise HTTPException(status_code=400,
                                detail="Cannot remove your own admin rights")
        user["is_admin"] = body.is_admin
    save_users(users)
    return {"updated": True}


@router.delete("/users/{username}")
def delete_user(username: str, current: dict = Depends(require_admin)):
    if username == current["username"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    users = load_users()
    if not any(u["username"] == username for u in users):
        raise HTTPException(status_code=404, detail="User not found")
    save_users([u for u in users if u["username"] != username])
    return {"deleted": True}
