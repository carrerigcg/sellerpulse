"""Armazenamento em memória por sessão de browser.

- InMemoryTokenStore: dict-backed, indexado por seller_id. Compatível
  DUCK-TYPED com src/auth.TokenStore no sentido de que satisfaz save()
  + load() → substituível diretamente no OAuthClient. Atenção: a
  substituição é UNIDIRECIONAL — código escrito contra InMemoryTokenStore
  usando o kwarg `seller_id=` NÃO funciona com o TokenStore de disco
  (que não conhece esse arg). Se precisarmos de intercâmbio bidirecional
  na Fase 6, definir um Protocol comum em src/auth.py.

- create_session_db: cria conexão SQLite :memory: com schema aplicado.

Este módulo não é thread-safe — assume acesso serializado dentro de uma
sessão Streamlit (o runtime do Streamlit garante isso naturalmente).
Não compartilhar instâncias via @st.cache_resource.
"""

from __future__ import annotations

import sqlite3

from src.auth import TokenSet
from src.storage import connect

# Sentinel para tokens salvos antes de sabermos o seller_id real (fluxo típico:
# exchange_code_for_tokens devolve tokens ANTES de chamarmos /users/me).
# Um set_seller_id(real_id) subsequente move a entrada pra key correta.
# Escolha do valor 0: seller_ids do ML são inteiros positivos assinados por
# eles; 0 não é usado. Se o ML mudar isso no futuro, trocar para -1 (também
# fora do espaço válido) ou para None (requer mudança no tipo do dict).
_ANONYMOUS_SELLER_ID = 0


class InMemoryTokenStore:
    """Store de tokens em memória — mesma interface de src/auth.TokenStore.

    Backing store é um dict indexado por seller_id (mesmo com uma entrada
    só em single-tenant; schema já preparado para multi-tenant do Fase 6).
    """

    def __init__(self) -> None:
        self._tokens_by_seller: dict[int, TokenSet] = {}
        # TODO(fase-6): single-valued current — se um dia precisarmos suportar
        # múltiplos sellers ativos por sessão (improvável no roadmap C→B), este
        # campo vira dict ou o "current" some (todo save/load exige seller_id).
        self._current_seller_id: int | None = None

    def save(self, tokens: TokenSet, *, seller_id: int | None = None) -> None:
        """Grava tokens para um seller_id específico.

        Se seller_id não é passado, usa/atualiza o `current` (útil pro fluxo
        onde o exchange acontece ANTES de saber o seller_id — depois um
        set_seller_id() amarra).
        """
        target = (
            seller_id if seller_id is not None else self._current_seller_id or _ANONYMOUS_SELLER_ID
        )
        self._tokens_by_seller[target] = tokens
        if self._current_seller_id is None:
            self._current_seller_id = target

    def load(self, *, seller_id: int | None = None) -> TokenSet:
        """Devolve TokenSet do seller. Levanta FileNotFoundError se vazio.

        Mantém contrato idêntico ao TokenStore de disco — permite plug-in
        direto no OAuthClient sem mudar chamadores.
        """
        target = seller_id if seller_id is not None else self._current_seller_id
        if target is None or target not in self._tokens_by_seller:
            raise FileNotFoundError("InMemoryTokenStore vazio — chame save() antes.")
        return self._tokens_by_seller[target]

    def set_seller_id(self, seller_id: int) -> None:
        """Amarra tokens salvos anonimamente (_ANONYMOUS_SELLER_ID) ao seller real.

        Fluxo típico: exchange_code_for_tokens devolve tokens; salvamos com
        save(tokens) (seller_id=_ANONYMOUS_SELLER_ID); depois chamamos
        /users/me e amarramos com set_seller_id(user_id).
        """
        if self._current_seller_id == seller_id:
            return
        if self._current_seller_id is not None:
            tokens = self._tokens_by_seller.pop(self._current_seller_id)
            self._tokens_by_seller[seller_id] = tokens
        self._current_seller_id = seller_id


def create_session_db() -> sqlite3.Connection:
    """Cria uma conexão SQLite :memory: com o schema do SellerPulse aplicado.

    Delega para storage.connect(":memory:") — assim qualquer PRAGMA ou
    row_factory adicionado em storage.py flui automaticamente pras
    sessões (evita divergência sutil entre Demo persistido e Real em memória).

    Uma conexão por chamada — cada sessão de browser tem a sua, isolada
    das outras. Quando a conn morre (GC), o SQLite in-memory some com ela.
    """
    return connect(":memory:")
