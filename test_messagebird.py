"""
Send a test SMS via the Bird Channels API.

Endpoint:
    POST https://api.bird.com/workspaces/{WORKSPACE_ID}/channels/{CHANNEL_ID}/messages

Setup:
    pip install requests python-dotenv
    Fill values in .env, then:
        python test_messagebird.py
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_KEY = os.getenv("BIRD_ACCESS_KEY", "").strip()
WORKSPACE_ID = os.getenv("WORKSPACE_ID", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
RECIPIENT = os.getenv("RECIPIENT", "").strip()

MESSAGE_TEXT = "Hello from Bird API test! If you got this, the access key works."


def send_sms() -> None:
    missing = [n for n, v in [
        ("BIRD_ACCESS_KEY", ACCESS_KEY),
        ("WORKSPACE_ID", WORKSPACE_ID),
        ("CHANNEL_ID", CHANNEL_ID),
        ("RECIPIENT", RECIPIENT),
    ] if not v]
    if missing:
        sys.exit(f"ERROR: missing in .env: {', '.join(missing)}")

    url = f"https://api.bird.com/workspaces/{WORKSPACE_ID}/channels/{CHANNEL_ID}/messages"
    headers = {
        "Authorization": f"AccessKey {ACCESS_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "body": {
            "type": "text",
            "text": {"text": MESSAGE_TEXT},
        },
        "receiver": {
            "contacts": [
                {
                    "identifierValue": RECIPIENT,
                    "identifierKey": "phonenumber",
                }
            ]
        },
    }

    print(f"POST {url}")
    print(f"Sending SMS to {RECIPIENT} ...")
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
    except requests.RequestException as e:
        sys.exit(f"Network error: {e}")

    print(f"HTTP {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        print(resp.text)
        return

    print(json.dumps(data, indent=2))

    if resp.status_code in (200, 201, 202):
        print("\nSUCCESS - request accepted by Bird API.")
    else:
        print("\nFAILED - check the error details above.")


if __name__ == "__main__":
    send_sms()
