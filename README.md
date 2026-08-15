# ConsultBae AI Automation Assignment

Merges 3 messy CSVs (Naukri applicants, gig workers, CBNexus contacts) into
one SQLite database, automates a duplicate-check flow with n8n, and runs a
mini audio submission app on top of the same database.

## Project structure
```
task1_merge/       Task 1 - merge pipeline + Task 4 data issues report
task2_n8n/          Task 2 - n8n workflow + the API it calls
task3_audio_app/    Task 3 - Flask audio submission app
task5_stretch_scaling.md   Task 5 - scaling analysis
data_issues_report.md      Task 4 deliverable (also copied into task1_merge/)
```

## Setup

### 1. Merge pipeline (Task 1)
```
cd task1_merge
pip install pandas python-dateutil
python3 merge_pipeline.py
```
Produces `people.db`, `data_issues_log.csv`, and `possible_duplicates_review.csv`.
Matching logic and every issue found is explained in `data_issues_report.md`.

### 2. Audio app (Task 3)
```
cd task3_audio_app
pip install -r requirements.txt
python3 app.py
```
Needs `ffmpeg` installed on the system (used by pydub for audio processing).
Open `http://127.0.0.1:5000`, submit a recording, then check
`http://127.0.0.1:5000/submissions`. Uses the same `people.db` from Task 1.

### 3. n8n automation (Task 2)
See `task2_n8n/README_task2.md` — full step-by-step for importing the
workflow, exposing the local API with ngrok, and testing it.

## Data issues found
Full writeup in `data_issues_report.md`. Short version: mixed phone formats,
inconsistent city names (Gurgaon/Gurugram etc.), a duplicate header row
mid-file, a column-shifted row, CTC values mixing rupees and lakhs, rate
values mixing per-hour and per-month, and several same-name people that
were deliberately *not* auto-merged because there was no reliable ID match
(flagged for manual review instead).

## Stuck log

1. **Problem:** After installing ffmpeg with `winget install ffmpeg`, running
   `ffmpeg -version` in the same terminal gave
   `ffmpeg : The term 'ffmpeg' is not recognized as the name of a cmdlet...`
   even though the install had clearly succeeded.
   **I asked with the claude** why a fresh install wasn't being picked up.
   **then I learn here:** winget updates the system PATH, but any terminal
   (or VS Code window) that was already open was started with the *old*
   PATH loaded into memory — it doesn't refresh on its own.
   **Then i fixid it:** fully closing VS Code (not just the terminal tab) and
   reopening it. The same problem came back later with `ngrok`, and the
   same fix worked — so this became a pattern I recognized the second time
   instead of getting stuck again.

2. **Problem:** `ngrok http 5001` failed with
   `Program 'ngrok.exe' failed to run: Operation did not complete
   successfully because the file contains a virus or potentially unwanted
   software`. ngrok is a legitimate tunneling tool, but Windows Defender
   flagged it as a threat and silently quarantined the executable.
   ** I asked with the Claude that:** what the error meant and whether ngrok was
   actually unsafe.
   **what  I got rejected here:** the tempting shortcut of just disabling Windows
   Defender entirely to make the error go away — that's a bigger security
   trade-off than the problem needed.
   **then I actually fixed it:** going into Windows Security → Protection
   history, finding the quarantined ngrok.exe, and restoring it, then
   adding a scoped exclusion for just that file (not the whole antivirus).

3. **Problem:** The audio app's mic recording appeared to work (button
   changed to "Stop recording", the player showed a waveform), but nothing
   played back, and the first real submission came through with
   `loudness_db: -94.6` — essentially silence — even though the pipeline
   itself (upload → ffmpeg feature extraction → database write) was
   working correctly end-to-end.
   **WHAT  I asked WITH THE  Claude:** whether this was a bug in `app.py`'s audio
   processing or something else.
   **What I checked first (and it wasn't the problem):** whether Chrome had
   mic permission for the site — it did.
   **THEN I actually fixed it:** Windows Settings → Privacy & security →
   Microphone → "Let desktop apps access your microphone" was toggled off,
   so the browser was granted a mic stream but got silence from it. Turning
   that on and restarting Chrome fixed it — confirmed by a real recording
   coming back with a normal (non-silent) loudness value on the next
   submission.

