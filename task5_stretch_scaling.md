# Stretch: Scaling the audio app to 5,000 gig workers over a weekend

*Current state: Flask dev server, SQLite, audio saved to local disk, feature
extraction runs synchronously inside the request.*

## What breaks first
1. **The dev server itself.** `python3 app.py` (Flask's built-in server) is
   single-process and not meant for concurrent traffic. The moment a few
   dozen people hit submit at once, requests start queueing and timing out —
   this is the first thing that falls over, probably within the first hour.
2. **Local disk storage.** Audio saved to a folder on one machine has a hard
   ceiling and no redundancy. At 5,000 workers submitting even 2 clips each
   (~3MB average for a short voice note), that's ~30,000MB / ~30GB minimum,
   likely more with retries — the disk fills up and/or the machine (if it's
   a small free-tier instance) runs out of space mid-weekend.
3. **SQLite write-locking.** SQLite allows only one writer at a time. Under
   concurrent submissions, writes start queueing behind each other and
   requests slow down or fail with "database is locked" errors.
4. **Synchronous audio processing.** Feature extraction (ffmpeg via pydub)
   runs inside the same request that's handling the upload. A slow/large
   file blocks that whole worker process, which compounds with the dev
   server problem above.
5. **No retry on flaky mobile networks.** Gig workers are likely uploading
   over patchy mobile data. A dropped connection mid-upload today just
   fails silently with no retry — the worker has to notice and redo it,
   and some will just give up, meaning lost submissions.

## Duplicates at scale
The Task 1 matching rule (exact phone match) still works fine here, but a
new failure mode appears: the **same person submitting the same recording
twice** because the upload appeared to fail on their end (no confirmation
shown fast enough) and they hit submit again. Fix: generate a client-side
idempotency key (or hash the audio content) so a retry doesn't create a
second row.

## What I'd change before a real launch
- **Object storage instead of local disk** (S3 / Cloudflare R2) for the
  audio files, so storage isn't tied to one server's disk and can scale
  independently.
- **Postgres instead of SQLite** — handles concurrent writes properly.
- **A production WSGI server (gunicorn) behind nginx**, running multiple
  worker processes, instead of the Flask dev server.
- **Move feature extraction to a background job queue** (e.g. Celery/RQ) —
  the upload request just saves the file and returns immediately;
  extraction happens async so one slow file doesn't block others.
- **Client-side retry + idempotency key** on the submit button so flaky
  mobile connections don't create duplicates or silent failures.
- **Basic rate limiting** per phone number, so one number can't spam
  hundreds of fake submissions.
- **Monitoring/alerting** (even something simple like Sentry for errors +
  a dashboard for submission count over time) — right now there's no way
  to know something broke until a worker complains.

## Cost shape
Storage cost scales roughly linearly with submissions (~30GB+ for the
weekend, growing every day after if nothing is archived/deleted). The
bigger cost risk is **bandwidth for playback** — every time someone
listens to a submission in the review UI, that's an egress cost; if
reviewers replay files often, this adds up faster than storage does.
Cheapest fix: compress audio to a lower bitrate on upload (users won't
notice on a voice note) and put a CDN in front of playback.
