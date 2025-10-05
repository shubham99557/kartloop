import os
import requests

NIMBUSPOST_API_USER_EMAIL = os.getenv("NIMBUSPOST_API_USER_EMAIL")
NIMBUSPOST_API_USER_PASSWORD = os.getenv("NIMBUSPOST_API_USER_PASSWORD")

BASE_URL = "https://api.nimbuspost.com/v1"

def get_auth_token():
    """
    Authenticate with Nimbuspost API and return a token.
    """
    auth_url = f"{BASE_URL}/authenticate"
    credentials = {
        "email": NIMBUSPOST_API_USER_EMAIL,
        "password": NIMBUSPOST_API_USER_PASSWORD
    }
    response = requests.post(auth_url, json=credentials)

    try:
        data = response.json()
    except ValueError:
        raise Exception(f"Non-JSON response from NimbusPost: {response.text}")

    if response.status_code == 200 and isinstance(data, dict):
        token = data.get("token")
        if not token:
            raise Exception(f"No token in response: {data}")
        return token
    else:
        raise Exception(f"Authentication failed: {data}")

def create_shipment(shipment_data):
    """
    Create a shipment using Nimbuspost API.
    """
    token = get_auth_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    shipment_url = f"{BASE_URL}/shipments"

    response = requests.post(shipment_url, headers=headers, json=shipment_data)

    try:
        return response.json()
    except ValueError:
        raise Exception(f"Non-JSON response when creating shipment: {response.text}")
