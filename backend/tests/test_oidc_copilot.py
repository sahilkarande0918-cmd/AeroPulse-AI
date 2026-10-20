"""OIDC/SSO bearer validation and the optional LLM explainer's outbound request (no network)."""
import json
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import security
from app.config import settings
from app.services import copilot

ISS, AUD = "https://idp.example.test/realms/aeropulse", "aeropulse-api"


@pytest.fixture
def oidc(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class StubJWKS:  # stands in for the IdP's JWKS endpoint
        def get_signing_key_from_jwt(self, token):
            return type("K", (), {"key": key.public_key()})()
    monkeypatch.setattr(settings, "auth_mode", "oidc")
    monkeypatch.setattr(settings, "oidc_issuer", ISS)
    monkeypatch.setattr(settings, "oidc_audience", AUD)
    monkeypatch.setattr(settings, "oidc_role_map", "mro-officers=officer,mro-analysts=analyst")
    monkeypatch.setattr(security, "_jwks", StubJWKS())

    def token(groups, *, signer=key, aud=AUD, exp=3600, user="sqn.ldr.demo"):
        claims = {"iss": ISS, "aud": aud, "sub": "uuid-1", "preferred_username": user, "name": "Demo SSO Officer",
                  "groups": groups, "exp": int(time.time()) + exp}
        return {"Authorization": "Bearer " + jwt.encode(claims, signer, algorithm="RS256")}
    return token


def test_oidc_token_maps_group_to_role_and_provisions_user(client, oidc):
    me = client.get("/api/auth/me", headers=oidc(["mro-officers", "unrelated"]))
    assert me.status_code == 200 and me.json()["role"] == "officer" and me.json()["username"] == "sqn.ldr.demo"
    assert "approve" in me.json()["permissions"]
    assert client.get("/api/auth/me", headers=oidc(["mro-analysts"])).json()["role"] == "analyst"   # IdP is source of truth


@pytest.mark.parametrize("case", ["wrong_audience", "expired", "foreign_signer"])
def test_oidc_rejects_bad_tokens(client, oidc, case):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    kw = {"wrong_audience": {"aud": "someone-else"}, "expired": {"exp": -60}, "foreign_signer": {"signer": other}}[case]
    assert client.get("/api/auth/me", headers=oidc(["mro-officers"], **kw)).status_code == 401


def test_oidc_without_mapped_group_is_forbidden_and_local_login_disabled(client, oidc):
    assert client.get("/api/auth/me", headers=oidc(["visitors"])).status_code == 403
    assert client.post("/api/auth/login", json={"username": "officer", "password": "x"}).status_code == 404


def test_copilot_sends_only_stored_facts_with_key_in_header(monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    seen = {}

    def handler(request: httpx.Request):
        seen["url"], seen["headers"], seen["body"] = str(request.url), request.headers, json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Advisory: s3 trend lowers RUL."}]}}]})
    answer = copilot.explain("why?", {"prediction": {"state": "VALID", "rul": 13.2}}, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert answer.startswith("Advisory")
    assert "test-key" not in seen["url"] and seen["headers"]["x-goog-api-key"] == "test-key"
    prompt = seen["body"]["contents"][0]["parts"][0]["text"]
    assert '"rul": 13.2' in prompt and "Never invent numbers" in seen["body"]["system_instruction"]["parts"][0]["text"]


def test_copilot_disabled_without_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(RuntimeError):
        copilot.explain("why?", {})
