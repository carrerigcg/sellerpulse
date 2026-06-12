"""OAuth do Mercado Livre — persistência e renovação de tokens."""
from __future__ import annotations

import json
import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

EXPIRY_SAFETY_MARGIN = timedelta(minutes=10)


@dataclass
class TokenSet:
    """Estado completo de credenciais OAuth para uma execução."""

    access_token: str
    refresh_token: str
    expires_at: datetime

    def is_expired(self) -> bool:
        """True se o token expirou OU está dentro da margem de segurança."""
        return datetime.now(timezone.utc) + EXPIRY_SAFETY_MARGIN >= self.expires_at

    def to_dict(self) -> dict[str, str]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "TokenSet":
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )


class TokenStore:
    """Lê e grava TokenSet em arquivo JSON local com ACL restrita."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def save(self, tokens: TokenSet) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(tokens.to_dict()), encoding="utf-8")
        _apply_user_only_acl(tmp)
        tmp.replace(self._path)

    def load(self) -> TokenSet:
        if not self._path.exists():
            raise FileNotFoundError(
                f"Arquivo de tokens não existe em {self._path}. "
                "Rodar `python -m src.setup_auth` primeiro."
            )
        data = json.loads(self._path.read_text(encoding="utf-8"))
        return TokenSet.from_dict(data)


def _apply_user_only_acl(path: Path) -> None:
    """Restringe permissões a apenas o usuário atual.

    Em Windows usa icacls. Em outros sistemas usa chmod 600.
    Falhas são silenciosas — a próxima execução tenta de novo.
    """
    try:
        if platform.system() == "Windows":
            user = os.environ.get("USERNAME", "")
            if user:
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
                    check=False, capture_output=True, timeout=5,
                )
        else:
            os.chmod(path, 0o600)
    except (OSError, subprocess.TimeoutExpired):
        pass


ML_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"


class OAuthError(Exception):
    """Falha no fluxo OAuth — refresh inválido ou erro de rede."""


class OAuthClient:
    """Coordena o ciclo de vida dos tokens (refresh + load + save)."""

    def __init__(self, *, client_id: str, client_secret: str, store: TokenStore) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._store = store

    def refresh(self) -> TokenSet:
        """Troca o refresh_token atual por um par novo. Persiste antes de retornar."""
        current = self._store.load()
        response = requests.post(
            ML_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": current.refresh_token,
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise OAuthError(
                f"Falha no refresh ({response.status_code}): {response.text[:200]}. "
                "Re-rodar `python -m src.setup_auth` para reautorizar."
            )
        data = response.json()
        new_tokens = TokenSet(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=int(data["expires_in"])),
        )
        # CRÍTICO: persistir antes de retornar.
        self._store.save(new_tokens)
        return new_tokens

    def exchange_code(self, *, code: str, redirect_uri: str) -> TokenSet:
        """Troca o `code` da autorização inicial por um par de tokens."""
        response = requests.post(
            ML_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise OAuthError(
                f"Falha no exchange ({response.status_code}): {response.text[:200]}"
            )
        data = response.json()
        tokens = TokenSet(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.now(timezone.utc)
            + timedelta(seconds=int(data["expires_in"])),
        )
        self._store.save(tokens)
        return tokens


def get_valid_access_token(oauth: OAuthClient) -> str:
    """Devolve um access_token sempre válido. Renova se necessário."""
    tokens = oauth._store.load()
    if tokens.is_expired():
        tokens = oauth.refresh()
    return tokens.access_token
