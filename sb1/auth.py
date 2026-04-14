"""OAuth2 + BankID authentication for SpareBank1 personal API."""

import json
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

TOKEN_FILE = Path.home() / ".sb1_token"
AUTH_URL = "https://api.sparebank1.no/oauth/authorize"
TOKEN_URL = "https://api.sparebank1.no/oauth/token"
REDIRECT_URI = "http://localhost:12345/callback"


def _load_token() -> dict | None:
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text())
    return None


def _save_token(token: dict) -> None:
    TOKEN_FILE.write_text(json.dumps(token, indent=2))
    TOKEN_FILE.chmod(0o600)


def _refresh(token: dict, client_id: str, client_secret: str) -> dict:
    r = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    r.raise_for_status()
    new_token = r.json()
    new_token["expires_at"] = time.time() + new_token.get("expires_in", 3600) - 60
    _save_token(new_token)
    return new_token


def _do_auth_flow(client_id: str, client_secret: str) -> dict:
    """Run BankID OAuth2 authorization code flow with local redirect server."""
    state = secrets.token_urlsafe(16)
    auth_params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "scope": "openid accounts transactions",
    }
    url = f"{AUTH_URL}?{urlencode(auth_params)}"

    code_holder: dict = {}
    server_ready = threading.Event()

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/callback":
                params = parse_qs(parsed.query)
                code_holder["code"] = params.get("code", [None])[0]
                code_holder["state"] = params.get("state", [None])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Authentication successful. You can close this tab.</h1>")
            else:
                self.send_response(404)
                self.end_headers()

    httpd = HTTPServer(("localhost", 12345), CallbackHandler)

    def serve():
        server_ready.set()
        httpd.handle_request()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    server_ready.wait()

    print(f"\nOpening browser for BankID login...\n{url}\n")
    webbrowser.open(url)

    t.join(timeout=120)

    if not code_holder.get("code"):
        raise RuntimeError("Auth flow timed out or no code received.")
    if code_holder.get("state") != state:
        raise RuntimeError("State mismatch — possible CSRF.")

    r = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code_holder["code"],
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    r.raise_for_status()
    token = r.json()
    token["expires_at"] = time.time() + token.get("expires_in", 3600) - 60
    _save_token(token)
    return token


def get_access_token() -> str:
    """Return a valid access token, refreshing or re-authing as needed."""
    client_id = os.environ.get("SB1_CLIENT_ID", "")
    client_secret = os.environ.get("SB1_CLIENT_SECRET", "")
    if not client_id:
        raise RuntimeError("SB1_CLIENT_ID not set. Add it to ~/.sb1_env or export it.")

    token = _load_token()

    if token and time.time() < token.get("expires_at", 0):
        return token["access_token"]

    if token and token.get("refresh_token"):
        try:
            return _refresh(token, client_id, client_secret)["access_token"]
        except Exception:
            pass

    token = _do_auth_flow(client_id, client_secret)
    return token["access_token"]


def login(client_id: str, client_secret: str) -> None:
    """Force a fresh BankID login."""
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    os.environ["SB1_CLIENT_ID"] = client_id
    os.environ["SB1_CLIENT_SECRET"] = client_secret
    _do_auth_flow(client_id, client_secret)
    print("✓ Authenticated and token saved to ~/.sb1_token")
