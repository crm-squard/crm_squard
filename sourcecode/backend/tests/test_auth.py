"""
測試多租戶帳號：Google 登入、session、RBAC（require_session/require_platform_role/
require_company_access）、/api/admin/companies、/api/admin/accounts。

Google ID token 驗證用 monkeypatch app.auth.verify_google_id_token 繞過（pytest 沒辦法真的
拿到一個有效的 Google ID token），只測我們自己這一段登入/session/RBAC 邏輯。
"""
import pytest
from fastapi.testclient import TestClient

from app import accounts_store
from app.main import app, _company_request_log, _request_log


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    _request_log.clear()
    _company_request_log.clear()
    yield
    _request_log.clear()
    _company_request_log.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_google_login_unknown_email_self_registers_as_tenant_primary(client, monkeypatch):
    """未知 email 首次登入要自動建立 tenant_primary 帳號（商家自助註冊），不是回 403。"""
    email = "nobody_pytest@example.com"
    monkeypatch.setattr("app.auth.verify_google_id_token", lambda token: email)

    resp = client.post("/api/auth/google", json={"id_token": "fake-token"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["account"]["email"] == email
    assert body["account"]["role"] == "tenant_primary"
    assert body["token"]

    account = accounts_store.get_account_by_email(email)
    assert account is not None
    accounts_store.delete_account(account["id"])


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
    def test_tenant_account_can_self_create_company_and_gets_bound(self, client, test_company):
        """商家帳號自助新增企業服務：建立成功、且自動綁定成為這家新公司的帳號。"""
        tenant = accounts_store.create_account("pytest_tenant_create@example.com", "tenant_primary", None)
        accounts_store.bind_company(tenant["id"], test_company["id"])
        token = accounts_store.create_session(tenant["id"])
        try:
            resp = client.post(
                "/api/admin/companies",
                json={"name": "商家自建的公司"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            new_company_id = resp.json()["id"]
            assert accounts_store.account_has_company_access(tenant, new_company_id)
        finally:
            accounts_store.delete_company(resp.json()["id"])
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

    def test_bound_tenant_can_delete_own_company(self, client, test_company):
        """商家帳號能刪除自己綁定的公司（自助建立公司後也要能自助刪除）。"""
        tenant = accounts_store.create_account("pytest_tenant_delete@example.com", "tenant_primary", None)
        accounts_store.bind_company(tenant["id"], test_company["id"])
        token = accounts_store.create_session(tenant["id"])
        try:
            resp = client.delete(
                f"/api/admin/companies/{test_company['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            assert accounts_store.get_company(test_company["id"]) is None
        finally:
            accounts_store.delete_account(tenant["id"])

    def test_unbound_tenant_cannot_delete_company(self, client, test_company):
        tenant = accounts_store.create_account("pytest_tenant_delete_denied@example.com", "tenant_primary", None)
        token = accounts_store.create_session(tenant["id"])
        try:
            resp = client.delete(
                f"/api/admin/companies/{test_company['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403
        finally:
            accounts_store.delete_account(tenant["id"])


class TestAuditLogApi:
    def test_bound_tenant_sees_company_audit_entries(self, client, test_company):
        tenant = accounts_store.create_account("pytest_tenant_audit@example.com", "tenant_primary", None)
        accounts_store.bind_company(tenant["id"], test_company["id"])
        token = accounts_store.create_session(tenant["id"])
        accounts_store.record_audit(
            tenant["id"], action="update_company", target_type="company", target_id=test_company["id"],
            detail={"name": "改名測試"},
        )
        try:
            resp = client.get(
                f"/api/admin/audit-log?company_id={test_company['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            entries = resp.json()["entries"]
            assert any(e["action"] == "update_company" for e in entries)
        finally:
            accounts_store.delete_account(tenant["id"])

    def test_unbound_tenant_cannot_see_company_audit_entries(self, client, test_company):
        tenant = accounts_store.create_account("pytest_tenant_audit_denied@example.com", "tenant_primary", None)
        token = accounts_store.create_session(tenant["id"])
        try:
            resp = client.get(
                f"/api/admin/audit-log?company_id={test_company['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403
        finally:
            accounts_store.delete_account(tenant["id"])


class TestListAccountsApi:
    """GET /api/admin/accounts：帶 company_id 查這家公司的協作帳號（不含管理者帳號），
    不帶則查全部管理者帳號（僅限 platform 角色）。"""

    def test_company_scoped_list_excludes_unbound_platform_accounts(
        self, client, test_company, platform_account
    ):
        """一般管理者帳號沒被綁定這家公司時，天生不會出現在協作帳號清單裡。"""
        tenant = accounts_store.create_account("pytest_accounts_company_scope@example.com", "tenant_primary", None)
        accounts_store.bind_company(tenant["id"], test_company["id"])
        token = accounts_store.create_session(tenant["id"])
        try:
            resp = client.get(
                f"/api/admin/accounts?company_id={test_company['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            emails = [a["email"] for a in resp.json()["accounts"]]
            assert tenant["email"] in emails
            assert platform_account["email"] not in emails
        finally:
            accounts_store.delete_account(tenant["id"])

    def test_platform_account_that_created_company_appears_in_its_account_list(
        self, client, platform_token, platform_account
    ):
        """管理者帳號自己建立公司時要自動綁定，讓這家公司的協作帳號清單能正常顯示、
        正常增減這個「創建者」（不受一般管理者帳號不綁定公司的預設行為影響）。"""
        create_resp = client.post(
            "/api/admin/companies",
            json={"name": "Pytest 管理者建立的公司"},
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        assert create_resp.status_code == 200
        company_id = create_resp.json()["id"]
        try:
            resp = client.get(
                f"/api/admin/accounts?company_id={company_id}",
                headers={"Authorization": f"Bearer {platform_token}"},
            )
            assert resp.status_code == 200
            emails = [a["email"] for a in resp.json()["accounts"]]
            assert platform_account["email"] in emails
        finally:
            accounts_store.delete_company(company_id)

    def test_company_scoped_list_excludes_other_companies_accounts(self, client, test_company):
        other_company = accounts_store.create_company("Pytest 其他公司", None)
        tenant_a = accounts_store.create_account("pytest_accounts_a@example.com", "tenant_primary", None)
        tenant_b = accounts_store.create_account("pytest_accounts_b@example.com", "tenant_primary", None)
        accounts_store.bind_company(tenant_a["id"], test_company["id"])
        accounts_store.bind_company(tenant_b["id"], other_company["id"])
        token_a = accounts_store.create_session(tenant_a["id"])
        try:
            resp = client.get(
                f"/api/admin/accounts?company_id={test_company['id']}",
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert resp.status_code == 200
            emails = [a["email"] for a in resp.json()["accounts"]]
            assert tenant_a["email"] in emails
            assert tenant_b["email"] not in emails
        finally:
            accounts_store.delete_account(tenant_a["id"])
            accounts_store.delete_account(tenant_b["id"])
            accounts_store.delete_company(other_company["id"])

    def test_unbound_tenant_cannot_list_company_accounts(self, client, test_company):
        tenant = accounts_store.create_account("pytest_accounts_unbound@example.com", "tenant_primary", None)
        token = accounts_store.create_session(tenant["id"])
        try:
            resp = client.get(
                f"/api/admin/accounts?company_id={test_company['id']}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 403
        finally:
            accounts_store.delete_account(tenant["id"])

    def test_no_company_id_lists_platform_accounts_only(self, client, platform_token, platform_account, test_company):
        tenant = accounts_store.create_account("pytest_accounts_platform_list@example.com", "tenant_primary", None)
        accounts_store.bind_company(tenant["id"], test_company["id"])
        try:
            resp = client.get(
                "/api/admin/accounts", headers={"Authorization": f"Bearer {platform_token}"}
            )
            assert resp.status_code == 200
            accounts = resp.json()["accounts"]
            assert all(a["role"] in ["platform_primary", "platform_secondary"] for a in accounts)
            assert any(a["email"] == platform_account["email"] for a in accounts)
            assert tenant["email"] not in [a["email"] for a in accounts]
        finally:
            accounts_store.delete_account(tenant["id"])

    def test_no_company_id_requires_platform_role(self, client):
        tenant = accounts_store.create_account("pytest_accounts_tenant_no_scope@example.com", "tenant_primary", None)
        token = accounts_store.create_session(tenant["id"])
        try:
            resp = client.get("/api/admin/accounts", headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 403
        finally:
            accounts_store.delete_account(tenant["id"])
