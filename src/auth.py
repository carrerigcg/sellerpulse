"""OAuth do Mercado Livre — persistência e renovação de tokens."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
        self._path.write_text(json.dumps(tokens.to_dict()), encoding="utf-8")
        _apply_user_only_acl(self._path)

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
    import os
    import platform
    import subprocess

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
