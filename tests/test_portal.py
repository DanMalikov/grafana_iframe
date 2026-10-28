"""Integration checks against the local Compose API and Grafana."""

import html
import http.client
import json
import re
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import jwt


ORIGIN = "http://127.0.0.1:8000"
PASSWORD_FILE = Path("/run/api-secrets/demo-password")


def request(method, path, *, body=None, headers=None, service="api", cookie=None):
    host, port = ("127.0.0.1", 8000) if service == "api" else ("grafana", 3000)
    connection = http.client.HTTPConnection(host, port, timeout=10)
    request_headers = headers.copy() if headers else {}
    if cookie:
        request_headers["Cookie"] = cookie
    connection.request(method, path, body=body, headers=request_headers)
    response = connection.getresponse()
    headers = {name.lower(): value for name, value in response.getheaders()}
    result = response.status, headers, response.read().decode()
    connection.close()
    return result


def iframe_token(page):
    match = re.search(r'<iframe[^>]+src="([^"]+)"', page)
    if match is None:
        raise AssertionError("Monitoring iframe missing")
    url = html.unescape(match.group(1))
    query = parse_qs(urlsplit(url).query)
    if "orgId" in query or "company_id" in query:
        raise AssertionError("Company selection leaked into iframe URL")
    if query.get("kiosk") != ["1"]:
        raise AssertionError("Grafana kiosk mode is not enabled")
    return query["auth_token"][0]


@unittest.skipUnless(PASSWORD_FILE.exists(), "Requires running Compose API")
class PortalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = PASSWORD_FILE.read_text(encoding="utf-8").strip()

    def sign_in(self, username):
        body = urlencode({"username": username, "password": self.password})
        status, headers, _ = request(
            "POST",
            "/portal/login",
            body=body,
            headers={
                "Origin": ORIGIN,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        self.assertEqual(status, 303)
        cookie = SimpleCookie()
        cookie.load(headers["set-cookie"])
        self.assertIn("portal_access_token", cookie)
        return cookie["portal_access_token"].value, headers["set-cookie"]

    def test_authentication_cookie_and_expiry(self):
        status, _, _ = request("GET", "/portal")
        self.assertEqual(status, 303)
        status, _, _ = request("GET", "/portal/monitoring")
        self.assertEqual(status, 303)

        body = urlencode({"username": "analyst1", "password": "wrong"})
        status, _, page = request(
            "POST",
            "/portal/login",
            body=body,
            headers={
                "Origin": ORIGIN,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        self.assertEqual(status, 401)
        self.assertIn("Неверный логин или пароль", page)

        token, set_cookie = self.sign_in("analyst1")
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=lax", set_cookie)
        self.assertIn("Path=/portal", set_cookie)
        self.assertIn("Max-Age=1800", set_cookie)
        cookie = f"portal_access_token={token}"
        status, _, page = request("GET", "/portal", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn("Company 1", page)

        claims = jwt.decode(token, options={"verify_signature": False})
        claims["exp"] = 1
        expired = jwt.encode(
            claims,
            Path("/run/api-secrets/jwt-secret").read_text().strip(),
            algorithm="HS256",
        )
        status, _, _ = request(
            "GET", "/portal", cookie=f"portal_access_token={expired}"
        )
        self.assertEqual(status, 303)
        status, _, _ = request(
            "GET", "/portal/monitoring", cookie=f"portal_access_token={expired}"
        )
        self.assertEqual(status, 303)

    def test_origin_and_logout(self):
        body = urlencode({"username": "analyst1", "password": self.password})
        for origin in (
            None,
            "null",
            "http://evil.example:8000",
            "https://127.0.0.1:8000",
            "http://127.0.0.1:8001",
        ):
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            if origin:
                headers["Origin"] = origin
            status, _, _ = request("POST", "/portal/login", body=body, headers=headers)
            self.assertEqual(status, 403)

        token, _ = self.sign_in("analyst1")
        cookie = f"portal_access_token={token}"
        status, _, _ = request("POST", "/portal/logout", cookie=cookie)
        self.assertEqual(status, 403)
        status, headers, _ = request(
            "POST", "/portal/logout", cookie=cookie, headers={"Origin": ORIGIN}
        )
        self.assertEqual(status, 303)
        self.assertIn("Max-Age=0", headers["set-cookie"])
        self.assertIn("Path=/portal", headers["set-cookie"])

        status, _, _ = request("GET", "/users/me", cookie=cookie)
        self.assertEqual(status, 403)
        status, _, _ = request(
            "GET", "/users/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(status, 200)

    def test_refresh_and_sequential_companies(self):
        status, headers, _ = request("GET", "/login", service="grafana")
        self.assertEqual(status, 200)
        self.assertEqual(headers["referrer-policy"], "no-referrer")

        grafana_cookie = None
        for company in ("1", "2"):
            token, _ = self.sign_in(f"analyst{company}")
            cookie = f"portal_access_token={token}"
            status, headers, page = request(
                "GET", "/portal/monitoring", cookie=cookie
            )
            self.assertEqual(status, 200)
            self.assertEqual(headers["cache-control"], "no-store")
            self.assertEqual(headers["referrer-policy"], "no-referrer")
            self.assertIn(f"Company {company}", page)
            grafana_token = iframe_token(page)
            claims = jwt.decode(grafana_token, options={"verify_signature": False})
            self.assertEqual(claims["company_id"], company)

            status, _, refreshed = request(
                "GET", "/portal/monitoring", cookie=cookie
            )
            self.assertEqual(status, 200)
            self.assertNotEqual(iframe_token(refreshed), grafana_token)

            status, grafana_headers, user_json = request(
                "GET",
                f"/api/user?{urlencode({'auth_token': grafana_token})}",
                service="grafana",
                cookie=grafana_cookie,
            )
            self.assertEqual(status, 200)
            expected_org = 3 if company == "1" else 4
            self.assertEqual(json.loads(user_json)["orgId"], expected_org)
            if "set-cookie" in grafana_headers:
                grafana_cookie = grafana_headers["set-cookie"].split(";", 1)[0]


if __name__ == "__main__":
    unittest.main()
