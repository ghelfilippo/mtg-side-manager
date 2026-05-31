from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from auth import (SESSION_COOKIE, SESSION_MAX_AGE, create_session,
                  get_current_user, get_user, verify_password)

router = APIRouter()


@router.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    user = get_user(username)
    if not user or not verify_password(password, user["password_hash"]):
        return RedirectResponse("/login?error=1", status_code=303)
    token = create_session(username)
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(SESSION_COOKIE, token, max_age=SESSION_MAX_AGE,
                    httponly=True, samesite="lax")
    return resp


@router.post("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "username": user["username"],
        "is_admin": user.get("is_admin", False),
        "archidekt_folder_id": user.get("archidekt_folder_id", ""),
    }
