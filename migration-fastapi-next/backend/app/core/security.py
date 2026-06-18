from datetime import datetime, timedelta
from typing import Annotated

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings
from app.db.mongo import get_db

cipher_suite = Fernet(settings.secret_key.encode())


def encrypt_token(token: str | None) -> str | None:
    if not token:
        return None
    return cipher_suite.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str | None) -> str | None:
    if not encrypted_token:
        return None
    try:
        return cipher_suite.decrypt(encrypted_token.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token criptografado inválido ou chave de criptografia incorreta.",
        ) from exc


def get_password_hash(password: str) -> str:
    password_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8"))


class CurrentUser(dict):
    @property
    def email(self) -> str:
        return self["email"]

    @property
    def is_admin(self) -> bool:
        return bool(self.get("is_admin", False))


async def get_current_user(x_user_email: Annotated[str | None, Header()] = None) -> CurrentUser:
    """Dependência temporária para migração.

    No Streamlit o usuário vive em session_state. Nesta base, o frontend envia
    X-User-Email enquanto a autenticação definitiva via JWT/SSO não é plugada.
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


def check_session_timeout(last_activity: datetime | None, timeout_minutes: int = 60) -> bool:
    if not last_activity:
        return False
    return datetime.utcnow() - last_activity > timedelta(minutes=timeout_minutes)
