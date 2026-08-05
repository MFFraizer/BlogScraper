#!/usr/bin/env python3
"""
Local GUI for scraper.py — a small Flask server with one page.

Run:
    python3 app.py
Then open:
    http://127.0.0.1:5000

Runs scraper.py as a subprocess and streams its console output to the
browser over SSE, so the existing CLI script never has to change.
"""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
SCRAPER_PATH = BASE_DIR / "scraper.py"

app = Flask(__name__)

# Single-job state — this is a personal, single-user local tool, so one
# scrape at a time is enough; no job queue/IDs needed.
_lock = threading.Lock()
_log_queue: "queue.Queue[str | None]" = queue.Queue()
_process: subprocess.Popen | None = None


def _run_scraper(url: str, author: str) -> None:
    global _process
    cmd = [sys.executable, str(SCRAPER_PATH), url]
    if author:
        cmd.append(author)

    proc = subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    _process = proc

    assert proc.stdout is not None
    for line in proc.stdout:
        _log_queue.put(line.rstrip("\n"))

    proc.wait()
    _log_queue.put(f"__DONE__{proc.returncode}")
    _log_queue.put(None)
    _process = None


@app.route("/")
def index():
    return send_from_directory(BASE_DIR / "templates", "index.html")


@app.route("/scrape", methods=["POST"])
def scrape():
    if not _lock.acquire(blocking=False):
        return jsonify({"error": "A scrape is already running."}), 409

    data = request.get_json(force=True) or {}
    url = (data.get("url") or "").strip()
    author = (data.get("author") or "").strip()

    if not url:
        _lock.release()
        return jsonify({"error": "URL is required."}), 400

    # Drain any stale messages from a previous run
    while not _log_queue.empty():
        _log_queue.get_nowait()

    def worker():
        try:
            _run_scraper(url, author)
        finally:
            _lock.release()

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/stream")
def stream():
    def generate():
        while True:
            item = _log_queue.get()
            if item is None:
                break
            yield f"data: {item}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/library")
def library():
    books = []
    for f in sorted(BASE_DIR.glob("*.epub"), key=lambda p: p.stat().st_mtime, reverse=True):
        books.append({
            "name": f.name,
            "size_kb": round(f.stat().st_size / 1024),
        })
    return jsonify(books)


@app.route("/library/<path:filename>")
def download(filename: str):
    safe_names = {f.name for f in BASE_DIR.glob("*.epub")}
    if filename not in safe_names:
        return jsonify({"error": "Not found."}), 404
    return send_from_directory(BASE_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
