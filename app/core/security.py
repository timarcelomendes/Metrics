from datetime import datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings
from app.db.mongo import get_db


class CurrentUser(dict):
    @property
    def email(self) -> str:
        return self["email"]

    @property
    def is_admin(self) -> bool:
        return bool(self.get("is_admin", False))


async def get_current_user(x_user_email: Annotated[str | None, Header()] = None) -> CurrentUser:
    """Dependência temporária para migração.

    Trocar por JWT, SSO ou login próprio na próxima etapa.
    """
    if not x_user_email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não autenticado.")

    email = x_user_email.strip().lower()
    db = get_db()
    user = db.users.find_one({"email": email}) or {"email": email}
    user["is_master"] = email in settings.master_user_list
    user["is_admin"] = bool(user.get("is_admin", False) or user["is_master"])
    user["last_activity_time"] = datetime.utcnow()
    db.users.update_one({"email": email}, {"$set": user}, upsert=True)
    return CurrentUser(user)


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores.")
    return user
