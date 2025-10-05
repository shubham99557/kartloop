# core/management/commands/test_nimbuspost.py
import json
import os
import requests
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Test NimbusPost shipment creation (login -> get token -> create shipment)"

    def _extract_token(self, data):
        """Try common places for token in the JSON response."""
        if not isinstance(data, dict):
            return None
        # top-level
        for key in ("token", "access_token", "auth_token"):
            if key in data and data[key]:
                return data[key]
        # nested in 'data'
        if "data" in data and isinstance(data["data"], dict):
            for key in ("token", "access_token", "auth_token"):
                if key in data["data"] and data["data"][key]:
                    return data["data"][key]
        # sometimes 'result' or 'response' contains token
        for container in ("result", "response"):
            if container in data and isinstance(data[container], dict):
                for key in ("token", "access_token", "auth_token"):
                    if key in data[container] and data[container][key]:
                        return data[container][key]
        return None

    def try_login_endpoints(self, base_url, email, password):
        """Try a few likely login endpoints and payloads to obtain token."""
        candidate_paths = [
            "/users/login",
            "/user/login",
            "/user_api/login",
            "/auth/login",
            "/authenticate",
            "/login",
        ]
        payload_variants = [
            {"email": email, "password": password},
            {"username": email, "password": password},
            {"user": {"email": email, "password": password}},
        ]
        headers = {"Content-Type": "application/json"}

        for path in candidate_paths:
            url = base_url.rstrip("/") + path
            for payload in payload_variants:
                try:
                    self.stdout.write(f"Trying login: POST {url} with payload keys: {list(payload.keys())}")
                    r = requests.post(url, headers=headers, json=payload, timeout=10)
                except Exception as e:
                    self.stdout.write(f"  request error: {e}")
                    continue

                # try parse JSON
                try:
                    data = r.json()
                except Exception:
                    data = r.text

                self.stdout.write(f"  status {r.status_code} response: {json.dumps(data) if isinstance(data, dict) else str(data)[:200]}")

                token = self._extract_token(data if isinstance(data, dict) else {})
                if token:
                    return token, url, data
        return None, None, None

    def handle(self, *args, **kwargs):
        base_url = getattr(settings, "NIMBUSPOST_API_URL", "").rstrip("/")
        api_key = getattr(settings, "NIMBUSPOST_API_KEY", "") or ""
        api_user_email = getattr(settings, "NIMBUSPOST_API_USER_EMAIL", "") or os.getenv("NIMBUSPOST_API_USER_EMAIL")
        api_user_password = getattr(settings, "NIMBUSPOST_API_USER_PASSWORD", "") or os.getenv("NIMBUSPOST_API_USER_PASSWORD")

        if not base_url:
            self.stdout.write(self.style.ERROR("❌ NIMBUSPOST_API_URL missing in settings/.env"))
            return

        self.stdout.write(f"Using API base URL: {base_url}")
        self.stdout.write(f"API key (masked): {api_key[:4] + '...' + api_key[-4:] if api_key else '(none)'}")
        self.stdout.write(f"API user email (masked): {api_user_email[:4] + '...' + api_user_email[-4:] if api_user_email else '(none)'}")

        token = None
        # 1) Preferred: login with API user (email/password) to get token
        if api_user_email and api_user_password:
            token, login_url, login_resp = self.try_login_endpoints(base_url, api_user_email, api_user_password)
            if token:
                self.stdout.write(self.style.SUCCESS(f"✅ Obtained token from login endpoint {login_url}"))
        else:
            self.stdout.write("No API user credentials provided (NIMBUSPOST_API_USER_EMAIL / _PASSWORD). Will try API-key-based fallback.")

        # 2) Fallback: sometimes the old API key is sent as Authorization: Token <key> or x-api-key header
        if not token and api_key:
            self.stdout.write("Trying fallback using API key directly (Token and x-api-key attempts).")
            # Try header 'Authorization: Token <api_key>'
            try_headers = [
                {"Content-Type": "application/json", "Authorization": f"Token {api_key}"},
                {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                {"Content-Type": "application/json", "x-api-key": api_key},
            ]

            sample_payload = {
                "order_number": "TEST123",
                "pickup_postcode": "110001",
                "delivery_postcode": "560001",
                "cod_amount": 0,
                "weight": 0.5,
                "length": 10,
                "breadth": 10,
                "height": 10,
                "payment_mode": "prepaid",
                "product_description": "Test Product",
                "consignee": {
                    "name": "Test User",
                    "address": "123 Test Street",
                    "city": "Bangalore",
                    "state": "Karnataka",
                    "mobile": "9999999999",
                    "email": "test@example.com"
                }
            }
            for hdr in try_headers:
                self.stdout.write(f"Trying direct shipment POST with headers: {list(hdr.keys())}")
                try:
                    resp = requests.post(f"{base_url}/shipments", headers=hdr, json=sample_payload, timeout=15)
                    try:
                        resp_data = resp.json()
                    except Exception:
                        resp_data = resp.text
                    self.stdout.write(f"  status {resp.status_code} resp: {json.dumps(resp_data) if isinstance(resp_data, dict) else str(resp_data)[:200]}")
                    # If response says token missing/invalid, continue. If success or different error, print and stop.
                    if resp.status_code in (200, 201):
                        self.stdout.write(self.style.SUCCESS("✅ Shipment created using direct API-key header."))
                        return
                except Exception as e:
                    self.stdout.write(f"  request error: {e}")

        # If we have a token (from login), use it to create shipment
        if token:
            self.stdout.write("Using token to create shipment (Authorization: Bearer <token>)")
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
            payload = {
                "order_number": "TEST123",
                "pickup_postcode": "110001",
                "delivery_postcode": "560001",
                "cod_amount": 0,
                "weight": 0.5,
                "length": 10,
                "breadth": 10,
                "height": 10,
                "payment_mode": "prepaid",
                "product_description": "Test Product",
                "consignee": {
                    "name": "Test User",
                    "address": "123 Test Street",
                    "city": "Bangalore",
                    "state": "Karnataka",
                    "mobile": "9999999999",
                    "email": "test@example.com"
                }
            }
            try:
                r = requests.post(f"{base_url}/shipments", headers=headers, json=payload, timeout=15)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Request failed: {e}"))
                return

            try:
                resp_data = r.json()
            except Exception:
                resp_data = r.text

            self.stdout.write(f"Shipment POST status: {r.status_code}")
            self.stdout.write(json.dumps(resp_data, indent=2) if isinstance(resp_data, dict) else str(resp_data))
            return

        # If we reach here we couldn't authenticate
        self.stdout.write(self.style.ERROR("❌ Could not obtain a valid token or use API key."))
        self.stdout.write("Please provide API user credentials (NIMBUSPOST_API_USER_EMAIL and NIMBUSPOST_API_USER_PASSWORD) or check the API Key from your NimbusPost dashboard.")
        self.stdout.write("If you want, send me your shipping/utils.py and a screenshot of the 'New API Document' (authentication) page and I will adjust this code to the exact expected flow.")
