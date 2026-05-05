"""
Keep-alive SMS sender for Bird (formerly MessageBird).

Sends an SMS to one or more Polish recipients to keep 2nr premium numbers
active. Each recipient has its own last-sent timestamp in state/last_sent.json,
so a message is only sent when the configured KEEP_ALIVE_HOURS threshold has
elapsed for that specific number.

Required env vars (read from environment or .env locally):
    BIRD_ACCESS_KEY   - Bird workspace access key
    WORKSPACE_ID      - Bird workspace UUID
    CHANNEL_ID        - SMS channel UUID
    RECIPIENTS        - comma-separated list of E.164 numbers, e.g.
                        "+48699556602,+48512345678"

Optional:
    KEEP_ALIVE_HOURS  - send threshold in hours (default 71)
    MESSAGE_TEXT      - text body (default "ping")
    STATE_FILE        - path to state file (default state/last_sent.json)
    FORCE             - "1" to ignore the threshold and send to everyone
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


ACCESS_KEY = os.getenv("BIRD_ACCESS_KEY", "").strip()
WORKSPACE_ID = os.getenv("WORKSPACE_ID", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
RECIPIENTS_RAW = os.getenv("RECIPIENTS", "").strip()
KEEP_ALIVE_HOURS = float(os.getenv("KEEP_ALIVE_HOURS", "71"))
MESSAGE_TEXT = os.getenv("MESSAGE_TEXT", "ping")
STATE_FILE = Path(os.getenv("STATE_FILE", "state/last_sent.json"))
FORCE = os.getenv("FORCE", "").strip() == "1"


def parse_recipients(raw: str) -> list[str]:
    nums = [n.strip() for n in raw.replace(";", ",").split(",")]
    return [n for n in nums if n]


def load_state() -> dict[str, str]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"WARNING: {STATE_FILE} is invalid JSON, starting fresh.")
    return {}


def save_state(state: dict[str, str]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def hours_since(iso_ts: str, now: datetime) -> float:
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return float("inf")
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds() / 3600.0


def send_sms(recipient: str) -> tuple[bool, dict | str]:
    url = f"https://api.bird.com/workspaces/{WORKSPACE_ID}/channels/{CHANNEL_ID}/messages"
    headers = {
        "Authorization": f"AccessKey {ACCESS_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "body": {"type": "text", "text": {"text": MESSAGE_TEXT}},
        "receiver": {
            "contacts": [
                {"identifierValue": recipient, "identifierKey": "phonenumber"}
            ]
        },
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
    except requests.RequestException as e:
        return False, f"network error: {e}"

    try:
        data = resp.json()
    except ValueError:
        data = resp.text

    ok = resp.status_code in (200, 201, 202)
    return ok, {"http": resp.status_code, "response": data}


def main() -> int:
    missing = [n for n, v in [
        ("BIRD_ACCESS_KEY", ACCESS_KEY),
        ("WORKSPACE_ID", WORKSPACE_ID),
        ("CHANNEL_ID", CHANNEL_ID),
        ("RECIPIENTS", RECIPIENTS_RAW),
    ] if not v]
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)}")
        return 2

    recipients = parse_recipients(RECIPIENTS_RAW)
    if not recipients:
        print("ERROR: no recipients parsed from RECIPIENTS.")
        return 2

    now = datetime.now(timezone.utc)
    state = load_state()
    any_failure = False
    sent_count = 0

    print(f"Run at {now.isoformat()} UTC")
    print(f"Threshold: {KEEP_ALIVE_HOURS}h | Force: {FORCE}")
    print(f"Recipients ({len(recipients)}): {', '.join(recipients)}")

    for number in recipients:
        last = state.get(number)
        if last and not FORCE:
            elapsed = hours_since(last, now)
            if elapsed < KEEP_ALIVE_HOURS:
                print(f"[skip ] {number}  last sent {elapsed:.1f}h ago (< {KEEP_ALIVE_HOURS}h)")
                continue
            print(f"[send ] {number}  last sent {elapsed:.1f}h ago")
        else:
            print(f"[send ] {number}  no prior record" if not FORCE else f"[force] {number}")

        ok, info = send_sms(number)
        if ok:
            state[number] = now.isoformat()
            sent_count += 1
            print(f"        OK  -> {info}")
        else:
            any_failure = True
            print(f"        FAIL -> {info}")

    save_state(state)
    print(f"Done. sent={sent_count}, failures={'yes' if any_failure else 'no'}")
    return 1 if any_failure else 0


if __name__ == "__main__":
    sys.exit(main())
