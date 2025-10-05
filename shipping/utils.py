import requests
import os
from django.conf import settings

class NimbusPostAPI:
    def __init__(self):
        self.base_url = "https://api.nimbuspost.com/v1"
        self.user_email = os.getenv(
            "NIMBUSPOST_API_USER_EMAIL",
            getattr(settings, "NIMBUSPOST_API_USER_EMAIL", None)
        )
        self.user_password = os.getenv(
            "NIMBUSPOST_API_USER_PASSWORD",
            getattr(settings, "NIMBUSPOST_API_USER_PASSWORD", None)
        )
        self.token = None

    # ------------------------
    # Internal Helpers
    # ------------------------
    def _parse_json(self, response, non_json_error="Non-JSON response from NimbusPost"):
        """Safely parse API JSON, wrap lists/other types into a dict."""
        try:
            data = response.json()
        except ValueError:
            return {
                "error": non_json_error,
                "status_code": response.status_code,
                "raw_response": response.text
            }
        return data if isinstance(data, dict) else {"data": data}

    def _extract_token(self, data):
        """Extract token from various API response formats."""
        if isinstance(data.get("token"), str):
            return data.get("token")
        if isinstance(data.get("access_token"), str):
            return data.get("access_token")
        if isinstance(data.get("data"), dict) and isinstance(data["data"].get("token"), str):
            return data["data"]["token"]
        if isinstance(data.get("data"), str):
            return data.get("data")  # 'data' is the token string
        return None

    # ------------------------
    # Authentication
    # ------------------------
    def authenticate(self):
        """Logs in and stores the Bearer token."""
        if not self.user_email or not self.user_password:
            return {"error": "Missing API credentials (email/password)"}

        login_url = f"{self.base_url}/users/login"
        payload = {"email": self.user_email, "password": self.user_password}

        try:
            r = requests.post(login_url, json=payload, timeout=15)
            r.raise_for_status()
            data = self._parse_json(r, non_json_error="Non-JSON authentication response")

            if "error" in data:
                return data

            token = self._extract_token(data)
            if not token:
                return {"error": "No token found in login response", "keys_present": list(data.keys())}

            self.token = token
            return {"success": True}

        except requests.RequestException as e:
            return {"error": f"Authentication request failed: {e}"}

    def get_headers(self):
        """Returns headers with Bearer token if authenticated."""
        if not self.token:
            auth_result = self.authenticate()
            if "error" in auth_result:
                return auth_result

        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }

    # ------------------------
    # Public API methods
    # ------------------------
    def get_courier_list(self):
        """Retrieves list of all couriers."""
        headers = self.get_headers()
        if "error" in headers:
            return headers
        try:
            r = requests.get(f"{self.base_url}/courier/all", headers=headers, timeout=15)
            r.raise_for_status()
            return self._parse_json(r)
        except requests.RequestException as e:
            return {"error": f"Request to NimbusPost failed: {e}"}

    def create_shipment(self, shipment_data):
        """Creates a shipment."""
        headers = self.get_headers()
        if "error" in headers:
            return headers
        try:
            r = requests.post(f"{self.base_url}/shipments", headers=headers, json=shipment_data, timeout=20)
            r.raise_for_status()
            return self._parse_json(r)
        except requests.RequestException as e:
            return {"error": f"Request to NimbusPost failed: {e}"}

    def track_shipment(self, awb_number):
        """Tracks a shipment by AWB number."""
        headers = self.get_headers()
        if "error" in headers:
            return headers
        try:
            r = requests.get(f"{self.base_url}/shipments/track/{awb_number}",
                             headers=headers, timeout=15)
            r.raise_for_status()
            return self._parse_json(r, non_json_error="Non-JSON tracking response from NimbusPost")
        except requests.RequestException as e:
            return {"error": f"Request to NimbusPost failed: {e}"}
