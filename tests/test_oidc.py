"""Signing in with Google or Microsoft (app/oidc.py), against a stand-in
provider: a real RSA key, discovery document and token endpoint, so the
signature, audience, issuer, expiry, nonce, state and PKCE checks all run
for real."""
from tests.base import *  # noqa: F401,F403
from tests.base import AppTestCase, client_for, count, make_user, one, uniq, user_id

import base64
import hashlib
import os
import time
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from app import oidc, security
from app.app import app
from app.db import SessionLocal
from app.models import UserAccount, UserIdentity

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
GOOGLE_ISS = "https://accounts.google.com"
MS_ISS_TEMPLATE = "https://login.microsoftonline.com/{tenantid}/v2.0"
ENV = {
    "BIOMANAGER_GOOGLE_CLIENT_ID": "google-client.apps.example",
    "BIOMANAGER_GOOGLE_CLIENT_SECRET": "google-secret",
    "BIOMANAGER_MICROSOFT_CLIENT_ID": "ms-client-id",
    "BIOMANAGER_MICROSOFT_CLIENT_SECRET": "ms-secret",
}
CONF = {
    "google": {"issuer": GOOGLE_ISS, "authorization_endpoint": "https://accounts.example/auth",
               "token_endpoint": "https://oauth2.example/token", "jwks_uri": "https://keys.example/google"},
    "microsoft": {"issuer": MS_ISS_TEMPLATE, "authorization_endpoint": "https://login.example/authorize",
                  "token_endpoint": "https://login.example/token", "jwks_uri": "https://keys.example/ms"},
}


class OidcCase(AppTestCase):
    def setUp(self):
        super().setUp()
        patches = [
            mock.patch.dict(os.environ, ENV),
            mock.patch.object(oidc, "_get_json", side_effect=self.fake_discovery),
            mock.patch.object(oidc, "_post_form", side_effect=self.fake_token_endpoint),
            mock.patch.object(oidc, "signing_key", return_value=KEY.public_key()),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        oidc._discovery.clear()
        self.token_requests = []
        self.next_token = None

    @staticmethod
    def fake_discovery(url):
        return CONF["microsoft" if "microsoftonline" in url else "google"]

    def fake_token_endpoint(self, url, data):
        self.token_requests.append((url, data))
        return {"id_token": self.next_token}

    def claims(self, provider, real_nonce, /, **overrides):
        now = int(time.time())
        base = {"sub": uniq("sub"), "iat": now, "exp": now + 300, "nonce": real_nonce,
                "email": f"{uniq('p')}@example.org", "email_verified": True, "name": "Pat Example"}
        if provider == "google":
            base.update(iss=GOOGLE_ISS, aud=ENV["BIOMANAGER_GOOGLE_CLIENT_ID"])
        else:
            base.update(iss="https://login.microsoftonline.com/tenant-1/v2.0", tid="tenant-1",
                        aud=ENV["BIOMANAGER_MICROSOFT_CLIENT_ID"])
        base.update(overrides)
        return base

    def begin(self, client, provider="google", query=""):
        r = client.get(f"/auth/{provider}/start{query}")
        self.assertEqual(r.status_code, 302, r.get_data(as_text=True)[:300])
        return r, {k: v[0] for k, v in parse_qs(urlparse(r.headers["Location"]).query).items()}

    def flow(self, client=None, provider="google", query="", sign_with=KEY, algorithm="RS256", token=None,
             state=None, **claim_overrides):
        """Start a sign-in, have the provider answer, and follow the callback."""
        client = client or app.test_client()
        _, params = self.begin(client, provider, query)
        claims = self.claims(provider, params["nonce"], **claim_overrides)
        if token is None:
            token = jwt.encode(claims, sign_with, algorithm=algorithm, headers={"kid": "k1"})
        self.next_token = token
        r = client.get(f"/auth/{provider}/callback?code=the-code&state={state or params['state']}",
                       follow_redirects=True)
        return client, r, claims

    def identity_user(self, claims):
        return one("select user_id_fk from user_identities where issuer=? and subject=?", claims["iss"], claims["sub"])

    def link(self, username, claims_sub, provider="google", iss=GOOGLE_ISS):
        with SessionLocal() as s:
            s.add(UserIdentity(user_id_fk=user_id(username), provider=provider, issuer=iss, subject=claims_sub))
            s.commit()

    def signed_in(self, client):
        return client.get("/settings").status_code == 200


class Starting(OidcCase):
    def test_an_unconfigured_provider_is_not_found(self):
        with mock.patch.dict(os.environ, {"BIOMANAGER_GOOGLE_CLIENT_ID": ""}):
            self.assertEqual(app.test_client().get("/auth/google/start").status_code, 404)
            self.assertNotIn("Sign in with Google", app.test_client().get("/login").get_data(as_text=True))

    def test_the_login_page_offers_configured_providers(self):
        html = app.test_client().get("/login").get_data(as_text=True)
        self.assertIn("Sign in with Google", html)
        self.assertIn("Sign in with Microsoft", html)

    def test_start_sends_state_nonce_and_a_pkce_challenge(self):
        client = app.test_client()
        r, params = self.begin(client)
        self.assertTrue(r.headers["Location"].startswith("https://accounts.example/auth?"))
        self.assertEqual(params["client_id"], ENV["BIOMANAGER_GOOGLE_CLIENT_ID"])
        self.assertEqual(params["redirect_uri"], "http://localhost/auth/google/callback")
        self.assertEqual(params["code_challenge_method"], "S256")
        self.assertEqual(params["scope"], "openid email profile")
        with client.session_transaction() as sess:
            pending = sess["oidc"]
        self.assertEqual(params["state"], pending["state"])
        self.assertEqual(params["nonce"], pending["nonce"])
        expected = base64.urlsafe_b64encode(hashlib.sha256(pending["verifier"].encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(params["code_challenge"], expected)

    def test_the_token_request_carries_the_code_and_the_pkce_verifier(self):
        client = app.test_client()
        _, params = self.begin(client)
        with client.session_transaction() as sess:
            verifier = sess["oidc"]["verifier"]
        self.next_token = jwt.encode(self.claims("google", params["nonce"]), KEY, algorithm="RS256")
        client.get(f"/auth/google/callback?code=the-code&state={params['state']}")
        url, data = self.token_requests[-1]
        self.assertEqual(url, CONF["google"]["token_endpoint"])
        self.assertEqual((data["code"], data["code_verifier"], data["grant_type"]),
                         ("the-code", verifier, "authorization_code"))

    def test_base_url_sets_the_redirect_uri(self):
        with mock.patch.dict(os.environ, {"BIOMANAGER_BASE_URL": "https://biomanager.example.ts.net"}):
            _, params = self.begin(app.test_client())
        self.assertEqual(params["redirect_uri"], "https://biomanager.example.ts.net/auth/google/callback")


class NewPeople(OidcCase):
    def test_an_unknown_account_becomes_a_request_waiting_for_approval(self):
        client, r, claims = self.flow()
        self.assertFlash(r, "A lab admin needs to approve it", "success")
        uid = self.identity_user(claims)
        self.assertIsNotNone(uid)
        role, disabled, pw = one("select role from users where id=?", uid), \
            one("select disabled from users where id=?", uid), one("select password_hash from users where id=?", uid)
        self.assertEqual((role, disabled, pw), ("pending", 1, security.NO_PASSWORD))
        self.assertFalse(self.signed_in(client))
        self.assertTrue(count("notifications", "recipient_username=? and message like ?", self.admin, "%with Google%"))

    def test_asking_again_signs_in_nobody_and_makes_no_second_account(self):
        client, r, claims = self.flow()
        before = count("users")
        _, r, _ = self.flow(sub=claims["sub"], email=claims["email"])
        self.assertFlash(r, "waiting for a lab admin to approve", "error")
        self.assertEqual(count("users"), before)

    def test_once_approved_they_sign_in(self):
        client, _, claims = self.flow()
        uid = self.identity_user(claims)
        self.post(self.a, f"/admin/users/{uid}/disable")  # approve
        client, r, _ = self.flow(sub=claims["sub"])
        self.assertTrue(self.signed_in(client))
        self.assertIsNotNone(one("select last_login_at from user_identities where user_id_fk=?", uid))

    def test_an_unverified_email_is_not_kept(self):
        _, _, claims = self.flow(email_verified=False)
        self.assertEqual(one("select email from users where id=?", self.identity_user(claims)), "")

    def test_usernames_are_made_unique(self):
        email = f"{uniq('same')}@example.org"
        _, _, a = self.flow(email=email)
        _, _, b = self.flow(email=email)
        names = {one("select username from users where id=?", self.identity_user(c)) for c in (a, b)}
        self.assertEqual(len(names), 2)

    def test_a_no_password_account_cannot_sign_in_with_a_password(self):
        _, _, claims = self.flow()
        username = one("select username from users where id=?", self.identity_user(claims))
        r = app.test_client().post("/login", data={"username": username, "password": security.NO_PASSWORD})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Incorrect username or password", r.get_data(as_text=True))


class SigningIn(OidcCase):
    def setUp(self):
        super().setUp()
        self.person = make_user_real()
        self.sub = uniq("sub")
        self.link(self.person, self.sub)

    def test_a_linked_account_signs_in_and_lands_on_next(self):
        client, r, _ = self.flow(sub=self.sub, query="?next=/plasmids")
        self.assertTrue(self.signed_in(client))
        self.assertEqual(urlparse(r.request.url).path, "/plasmids")

    def test_next_cannot_leave_the_site(self):
        client, r, _ = self.flow(sub=self.sub, query="?next=//evil.example")
        self.assertNotIn("evil", r.request.url)

    def test_google_issuer_without_scheme_is_accepted(self):
        client, _, _ = self.flow(sub=self.sub, iss="accounts.google.com")
        self.assertTrue(self.signed_in(client))

    def test_disabled_accounts_stay_out(self):
        execute("update users set disabled=true where username=?", self.person)
        client, r, _ = self.flow(sub=self.sub)
        self.assertFlash(r, "disabled", "error")
        self.assertFalse(self.signed_in(client))

    def refused(self, **kwargs):
        client, r, _ = self.flow(sub=self.sub, **kwargs)
        self.assertFalse(self.signed_in(client), kwargs)
        self.assertFlash(r, "did not work", "error")

    def test_a_token_for_another_app_is_refused(self):
        self.refused(aud="someone-elses-client")

    def test_a_token_from_another_issuer_is_refused(self):
        self.refused(iss="https://evil.example")

    def test_a_token_from_another_sign_in_is_refused(self):
        self.refused(nonce="a-different-nonce")

    def test_an_expired_token_is_refused(self):
        now = int(time.time())
        self.refused(iat=now - 7200, exp=now - 3600)

    def test_a_token_signed_by_another_key_is_refused(self):
        self.refused(sign_with=OTHER_KEY)

    def test_an_unsigned_token_is_refused(self):
        client = app.test_client()
        _, params = self.begin(client)
        token = jwt.encode(self.claims("google", params["nonce"], sub=self.sub), None, algorithm="none")
        self.next_token = token
        r = client.get(f"/auth/google/callback?code=c&state={params['state']}", follow_redirects=True)
        self.assertFalse(self.signed_in(client))

    def test_a_shared_secret_token_is_refused(self):
        self.refused(sign_with="a shared secret at least thirty-two bytes long", algorithm="HS256")

    def test_a_wrong_state_is_refused_before_the_code_is_used(self):
        client, r, _ = self.flow(sub=self.sub, state="forged-state")
        self.assertFalse(self.signed_in(client))
        self.assertFlash(r, "was not started here", "error")
        self.assertEqual(self.token_requests, [])

    def test_a_sign_in_left_too_long_expires(self):
        client = app.test_client()
        _, params = self.begin(client)
        with client.session_transaction() as sess:
            pending = sess["oidc"]
            pending["started"] -= oidc.SIGN_IN_WINDOW + 5
            sess["oidc"] = pending
        r = client.get(f"/auth/google/callback?code=c&state={params['state']}", follow_redirects=True)
        self.assertFlash(r, "expired", "error")

    def test_a_cancelled_sign_in_says_so(self):
        client = app.test_client()
        self.begin(client)
        r = client.get("/auth/google/callback?error=access_denied", follow_redirects=True)
        self.assertFlash(r, "cancelled", "error")

    def test_a_callback_nobody_started_is_refused(self):
        r = app.test_client().get("/auth/google/callback?code=c&state=x", follow_redirects=True)
        self.assertFlash(r, "was not started here", "error")


class Microsoft(OidcCase):
    def test_the_tenant_in_the_token_fills_the_issuer_template(self):
        person, sub = make_user_real(), uniq("sub")
        self.link(person, sub, provider="microsoft", iss="https://login.microsoftonline.com/tenant-1/v2.0")
        client, _, _ = self.flow(provider="microsoft", sub=sub)
        self.assertTrue(self.signed_in(client))

    def test_a_token_whose_issuer_is_another_tenant_is_refused(self):
        client, r, _ = self.flow(provider="microsoft", iss="https://login.microsoftonline.com/tenant-2/v2.0")
        self.assertFalse(self.signed_in(client))
        self.assertFlash(r, "did not work", "error")

    def test_an_unexpected_tenant_setting_is_refused(self):
        with mock.patch.dict(os.environ, {"BIOMANAGER_MICROSOFT_TENANT": "../evil"}):
            with self.assertRaises(RuntimeError):
                oidc.providers()


class ConnectingFromSettings(OidcCase):
    def test_a_signed_in_person_connects_an_account(self):
        person = make_user_real()
        client = client_for(person)
        _, r, claims = self.flow(client=client, query="?link=1")
        self.assertFlash(r, "account connected", "success")
        self.assertEqual(self.identity_user(claims), user_id(person))
        self.assertIn("Disconnect", self.get_ok(client, "/settings"))

    def test_an_account_connected_to_someone_else_is_refused(self):
        owner, sub = make_user_real(), uniq("sub")
        self.link(owner, sub)
        client = client_for(make_user_real())
        _, r, _ = self.flow(client=client, query="?link=1", sub=sub)
        self.assertFlash(r, "already connected to another", "error")
        self.assertEqual(count("user_identities", "subject=?", sub), 1)

    def test_connecting_needs_a_signed_in_person(self):
        r = app.test_client().get("/auth/google/start?link=1")
        self.assertIn("/login", r.headers["Location"])

    def identity_id(self, username):
        return one("select id from user_identities where user_id_fk=?", user_id(username))

    def test_disconnecting_with_a_password_to_fall_back_on(self):
        person = make_user_real()
        self.link(person, uniq("sub"))
        r = self.post(client_for(person), f"/auth/identities/{self.identity_id(person)}/disconnect")
        self.assertFlash(r, "disconnected", "success")
        self.assertEqual(count("user_identities", "user_id_fk=?", user_id(person)), 0)

    def test_the_last_way_in_cannot_be_disconnected(self):
        _, _, claims = self.flow()
        uid = self.identity_user(claims)
        self.post(self.a, f"/admin/users/{uid}/disable")  # approve
        username = one("select username from users where id=?", uid)
        r = self.post(client_for(username), f"/auth/identities/{self.identity_id(username)}/disconnect")
        self.assertFlash(r, "Set a password first", "error")
        self.assertEqual(count("user_identities", "user_id_fk=?", uid), 1)

    def test_someone_elses_identity_cannot_be_disconnected(self):
        owner = make_user_real()
        self.link(owner, uniq("sub"))
        r = client_for(make_user_real()).post(f"/auth/identities/{self.identity_id(owner)}/disconnect")
        self.assertEqual(r.status_code, 404)

    def test_a_no_password_account_can_set_one_without_a_current_password(self):
        _, _, claims = self.flow()
        uid = self.identity_user(claims)
        self.post(self.a, f"/admin/users/{uid}/disable")
        username = one("select username from users where id=?", uid)
        client = client_for(username)
        self.assertIn("Set a password", self.get_ok(client, "/settings"))
        new = "a brand new passphrase"
        r = self.post(client, "/settings", data={"action": "password", "new_password": new, "confirm_password": new})
        self.assertFlash(r, "Password updated", "success")
        ok = app.test_client().post("/login", data={"username": username, "password": new})
        self.assertEqual(ok.status_code, 302)


def make_user_real() -> str:
    """A signed-up member with a real password (make_user's "x" is not a hash)."""
    from werkzeug.security import generate_password_hash
    username = uniq("real")
    with SessionLocal() as s:
        s.add(UserAccount(username=username, password_hash=generate_password_hash("correct horse battery"), role="member"))
        s.commit()
    return username


if __name__ == "__main__":
    unittest.main()
