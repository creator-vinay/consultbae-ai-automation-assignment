"""
duplicate_check_api.py -- tiny API that the n8n workflow calls.

n8n itself has no easy way to query SQLite directly, so this is the bridge:
n8n sends {name, email, phone} for each row of a new incoming CSV, this
returns whether that person already exists in people.db (using the exact
same email/phone matching rule from Task 1's merge_pipeline.py).

Run:  python3 duplicate_check_api.py   (listens on port 5001)
Then either:
  - point n8n (self-hosted, same machine) at http://localhost:5001/check
  - or expose it with ngrok if using n8n Cloud: `ngrok http 5001`
    and use the printed https://...ngrok-free.app/check URL in the HTTP node.
"""
import sqlite3
import os
from flask import Flask, request, jsonify

from normalize import normalize_email, normalize_phone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "people.db")

app = Flask(__name__)


@app.route("/check", methods=["POST"])
def check():
    data = request.get_json(force=True) or {}
    email = normalize_email(data.get("email"))
    phone = normalize_phone(data.get("phone"))
    name = data.get("name")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    match = None
    if email:
        cur.execute("SELECT * FROM people WHERE email = ?", (email,))
        match = cur.fetchone()
    if not match and phone:
        cur.execute("SELECT * FROM people WHERE phone = ?", (phone,))
        match = cur.fetchone()
    conn.close()

    if match:
        return jsonify({
            "duplicate": True,
            "matched_on": "email" if email and match["email"] == email else "phone",
            "existing_person_id": match["person_id"],
            "existing_name": match["name"],
            "incoming_name": name,
        })
    return jsonify({"duplicate": False, "incoming_name": name})


if __name__ == "__main__":
    app.run(port=5001, debug=True)
