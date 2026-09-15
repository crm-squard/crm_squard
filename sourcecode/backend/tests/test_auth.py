"""
測試多租戶帳號：Google 登入、session、RBAC（require_session/require_platform_role/
require_company_access）、/api/admin/companies、/api/admin/accounts。

Google ID token 驗證用 monkeypatch app.auth.verify_google_id_token 繞過（pytest 沒辦法真的
拿到一個有效的 Google ID token），只測我們自己這一段登入/session/RBAC 邏輯。
"""
import pytest
from fastapi.testclient import TestClient

from app import accounts_store
from app.main import app, _request_log


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    _request_log.clear()
    yield
    _request_log.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_google_login_unknown_email_returns_403(client, monkeypatch):
    """帳號沒有被手動加入系統時，登入要回 403（不是自動建立帳號）。"""
    monkeypatch.setattr("app.auth.verify_google_id_token", lambda token: "nobody_pytest@example.com")

    resp = client.post("/api/auth/google", json={"id_token": "fake-token"})

    assert resp.status_code == 403


def test_google_login_known_email_returns_session_token(client, monkeypatch, platform_account):
    monkeypatch.setattr("app.auth.verify_google_id_token", lambda token: platform_account["email"])

    resp = client.post("/api/auth/google", json={"id_token": "fake-token"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["account"]["email"] == platform_account["email"]
    assert body["account"]["role"] == "platform_primary"
    assert body["token"]

    # 拿到的 token 應該能直接用在 /api/auth/me
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["account"]["email"] == platform_account["email"]


def test_me_without_authorization_header_returns_401(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_invalid_token_returns_401(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_logout_revokes_session(client, platform_account):
    token = accounts_store.create_session(platform_account["id"])
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    logout_resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_resp.status_code == 200

    after_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert after_resp.status_code == 401


def test_delete_account_immediately_revokes_its_sessions():
    """移除帳號要立刻讓對方的 session 失效（不是等 token 自然過期），靠 ON DELETE CASCADE。"""
    account = accounts_store.create_account("pytest_revoke_target@example.com", "platform_secondary", None)
    token = accounts_store.create_session(account["id"])
    assert accounts_store.get_account_by_session(token) is not None

    accounts_store.delete_account(account["id"])

    assert accounts_store.get_account_by_session(token) is None


class TestCompanyAccess:
    """require_company_access：platform 帳號可跨公司、tenant 帳號跨公司會 403、同公司可通過。"""

    def test_platform_account_can_access_any_company(self, client, platform_token, test_company):
        resp = client.get(
            "/api/admin/documents",
            params={"company_id": test_company["id"]},
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        assert resp.status_code == 200

    def test_tenant_account_without_binding_gets_403(self, client, test_company):
        tenant = accounts_store.create_account("pytest_tenant_unbound@example.com", "tenant_primary", None)
        token = accounts_store.create_session(tenant["id"])
        try:
            resp = client.get(
                "/api/admin/documents",
                params={"company_id": test_company["id"]},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403
        finally:
            accounts_store.delete_account(tenant["id"])

    def test_tenant_account_with_binding_can_access(self, client, test_company):
        tenant = accounts_store.create_account("pytest_tenant_bound@example.com", "tenant_primary", None)
        accounts_store.bind_company(tenant["id"], test_company["id"])
        token = accounts_store.create_session(tenant["id"])
        try:
            resp = client.get(
                "/api/admin/documents",
                params={"company_id": test_company["id"]},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
        finally:
            accounts_store.delete_account(tenant["id"])

    def test_missing_authorization_header_returns_401_not_403(self, client, test_company):
        """完全沒帶 token：應該是 401（沒登入），不是 403（有登入但沒權限），錯誤語意要分清楚。"""
        resp = client.get("/api/admin/documents", params={"company_id": test_company["id"]})
        assert resp.status_code == 401


class TestCompaniesApi:
    def test_create_company_requires_platform_role(self, client, test_company):
        tenant = accounts_store.create_account("pytest_tenant_create@example.com", "tenant_primary", None)
        accounts_store.bind_company(tenant["id"], test_company["id"])
        token = accounts_store.create_session(tenant["id"])
        try:
            resp = client.post(
                "/api/admin/companies",
                json={"name": "應該被拒絕的公司"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403
        finally:
            accounts_store.delete_account(tenant["id"])

    def test_platform_account_creates_company_and_lists_it(self, client, platform_token):
        create_resp = client.post(
            "/api/admin/companies",
            json={"name": "Pytest 測試商家", "mcp_url": "https://example.com/mcp"},
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        assert create_resp.status_code == 200
        company = create_resp.json()
        assert company["name"] == "Pytest 測試商家"
        assert company["mcp_url"] == "https://example.com/mcp"

        try:
            list_resp = client.get(
                "/api/admin/companies", headers={"Authorization": f"Bearer {platform_token}"}
            )
            assert list_resp.status_code == 200
            ids = [c["id"] for c in list_resp.json()["companies"]]
            assert company["id"] in ids
        finally:
            accounts_store.delete_company(company["id"])

    def test_tenant_account_only_sees_bound_companies(self, client, test_company):
        other = accounts_store.create_company("Pytest 不該看到的公司", None)
        tenant = accounts_store.create_account("pytest_tenant_visibility@example.com", "tenant_primary", None)
        accounts_store.bind_company(tenant["id"], test_company["id"])
        token = accounts_store.create_session(tenant["id"])
        try:
            resp = client.get("/api/admin/companies", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 200
            ids = {c["id"] for c in resp.json()["companies"]}
            assert test_company["id"] in ids
            assert other["id"] not in ids
        finally:
            accounts_store.delete_account(tenant["id"])
            accounts_store.delete_company(other["id"])

    def test_delete_company_requires_platform_role(self, client, test_company):
        tenant = accounts_store.create_account("pytest_tenant_delete@example.com", "tenant_primary", None)
        accounts_store.bind_company(tenant["id"], test_company["id"])
        token = accounts_store.create_session(tenant["id"])
        try:
            resp = client.delete(
                f"/api/admin/companies/{test_company['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403
        finally:
            accounts_store.delete_account(tenant["id"])
