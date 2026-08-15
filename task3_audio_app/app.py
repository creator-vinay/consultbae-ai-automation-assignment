"""
app.py -- Task 3: Mini audio collection app

Flow:
  GET  /            -> form: name, phone, record (mic) or upload a file
  POST /submit       -> saves the audio file, extracts duration/sample rate/
                         bitrate/loudness with pydub+ffmpeg, links to (or
                         creates) a person in people.db, stores the row
  GET  /submissions  -> lists every submission with a play button + the
                         extracted numbers

Run:
  python3 app.py
  open http://127.0.0.1:5000
"""
import os
import sqlite3
import uuid
from datetime import datetime, timezone

from flask import Flask, request, render_template, redirect, url_for, send_from_directory
from pydub import AudioSegment

from normalize import normalize_phone, normalize_name

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "people.db")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25MB cap per upload


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def find_or_create_person(conn, name, phone):
    """Reuse the Task 1 matching rule: exact phone match only, else create new."""
    cur = conn.cursor()
    if phone:
        cur.execute("SELECT person_id FROM people WHERE phone = ?", (phone,))
        row = cur.fetchone()
        if row:
            return row["person_id"]
    cur.execute(
        "INSERT INTO people (name, email, phone, city, sources) VALUES (?, NULL, ?, NULL, 'audio_app')",
        (name, phone),
    )
    conn.commit()
    return cur.lastrowid


def extract_audio_features(filepath):
    """Returns (duration_sec, sample_rate_khz, bitrate_kbps, loudness_db, quality_estimate)."""
    audio = AudioSegment.from_file(filepath)

    duration_sec = round(len(audio) / 1000.0, 2)
    sample_rate_khz = round(audio.frame_rate / 1000.0, 2)

    file_size_bits = os.path.getsize(filepath) * 8
    bitrate_kbps = round((file_size_bits / duration_sec) / 1000.0, 1) if duration_sec > 0 else 0

    # dBFS = loudness relative to the max possible level (0 dB = loudest possible, more
    # negative = quieter). This is the standard way pydub/ffmpeg reports loudness.
    loudness_db = round(audio.dBFS, 1) if audio.dBFS != float("-inf") else -96.0

    # Rough quality/noise estimate (bonus): compare loud parts vs quiet parts.
    # A clean recording of speech has a decent gap between average and quietest
    # moments; a noisy/flat recording does not.
    try:
        chunk_ms = 100
        chunks = [audio[i:i + chunk_ms].dBFS for i in range(0, len(audio), chunk_ms)]
        chunks = [c for c in chunks if c != float("-inf")]
        if len(chunks) >= 2:
            dynamic_range = max(chunks) - min(chunks)
            if dynamic_range > 25:
                quality = "good (clear speech, low background noise)"
            elif dynamic_range > 12:
                quality = "okay (some background noise)"
            else:
                quality = "poor (flat/noisy, little difference between speech and silence)"
        else:
            quality = "unknown (clip too short to estimate)"
    except Exception:
        quality = "unknown"

    return duration_sec, sample_rate_khz, bitrate_kbps, loudness_db, quality


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/submit", methods=["POST"])
def submit():
    name_raw = request.form.get("name", "").strip()
    phone_raw = request.form.get("phone", "").strip()
    audio_file = request.files.get("audio")

    if not name_raw or not phone_raw or not audio_file:
        return "Name, phone and an audio file/recording are all required.", 400

    name = normalize_name(name_raw)
    phone = normalize_phone(phone_raw)

    ext = os.path.splitext(audio_file.filename or "")[1] or ".webm"
    safe_filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(UPLOAD_DIR, safe_filename)
    audio_file.save(filepath)

    try:
        duration, sample_rate_khz, bitrate, loudness, quality = extract_audio_features(filepath)
    except Exception as e:
        os.remove(filepath)
        return f"Could not read that audio file (ffmpeg error): {e}", 400

    conn = get_db()
    person_id = find_or_create_person(conn, name, phone)
    conn.execute(
        "INSERT INTO audio_submissions (person_id, name, phone, filename, duration_sec, "
        "sample_rate_khz, bitrate_kbps, loudness_db, quality_estimate, submitted_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (person_id, name, phone_raw, safe_filename, duration, sample_rate_khz,
         bitrate, loudness, quality, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("submissions"))


@app.route("/submissions")
def submissions():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM audio_submissions ORDER BY submitted_at DESC"
    ).fetchall()
    conn.close()
    return render_template("list.html", rows=rows)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
