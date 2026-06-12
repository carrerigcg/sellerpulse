"""Script standalone para autorização inicial do app no Mercado Livre.

Executar UMA VEZ na configuração inicial:
    python -m src.setup_auth
"""
from __future__ import annotations

import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

from src.auth import OAuthClient, TokenStore

REDIRECT_HOST = "localhost"
REDIRECT_PORT = 8080
REDIRECT_PATH = "/callback"
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}{REDIRECT_PATH}"
TOKENS_PATH = Path("data/tokens.json")

ML_AUTH_URL_TEMPLATE = (
    "https://auth.mercadolivre.com.br/authorization?"
    "response_type=code&client_id={client_id}&redirect_uri={redirect_uri}"
)


class _CallbackHandler(BaseHTTPRequestHandler):
    captured_code: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != REDIRECT_PATH:
            self.send_response(404)
            self.end_headers()
            return
        params = parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        type(self).captured_code = code
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = (
            "<h1>Autorização concluída.</h1>"
            "<p>Pode fechar essa aba e voltar ao terminal.</p>"
        )
        self.wfile.write(msg.encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return  # silencia logs do http.server


def _capture_code() -> str:
    server = HTTPServer((REDIRECT_HOST, REDIRECT_PORT), _CallbackHandler)
    try:
        server.handle_request()  # processa uma requisição e sai
    finally:
        server.server_close()
    if _CallbackHandler.captured_code is None:
        raise RuntimeError("Callback recebido sem 'code'. Tente novamente.")
    return _CallbackHandler.captured_code


def main() -> int:
    load_dotenv()
    client_id = os.environ.get("ML_CLIENT_ID")
    client_secret = os.environ.get("ML_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("ERRO: defina ML_CLIENT_ID e ML_CLIENT_SECRET no .env", file=sys.stderr)
        return 1

    auth_url = ML_AUTH_URL_TEMPLATE.format(
        client_id=client_id, redirect_uri=REDIRECT_URI
    )
    print("Abrindo o navegador para autorização do app no Mercado Livre...")
    print(f"Se não abrir, acesse manualmente: {auth_url}")
    webbrowser.open(auth_url)
    print(f"Aguardando callback em {REDIRECT_URI} ...")
    code = _capture_code()
    print(f"Código recebido. Trocando por tokens...")

    store = TokenStore(TOKENS_PATH)
    oauth = OAuthClient(client_id=client_id, client_secret=client_secret, store=store)
    tokens = oauth.exchange_code(code=code, redirect_uri=REDIRECT_URI)
    print(f"Tokens salvos em {TOKENS_PATH}. Expiram em {tokens.expires_at}.")
    print("Pronto. Já pode rodar `python -m src.main`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
