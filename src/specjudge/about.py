"""Authorship metadata shown in the reports.

Single source of truth so the terminal and the HTML view never drift apart.
Kept deliberately small and unobtrusive: the report is the user's answer, not
an ad. The JSON output carries none of this — it is meant for scripting.
"""

from __future__ import annotations

AUTHOR = "Joaquín Ruiz"
SITE = "jokiruiz.com"
SITE_URL = "https://jokiruiz.com"
YOUTUBE = "youtube.com/@jokioki"
YOUTUBE_URL = "https://youtube.com/@jokioki"

BOOKS: list[dict[str, str]] = [
    {
        "title": "El motor de la Inteligencia Artificial",
        "url": "https://amzn.eu/d/083CTN3U",
        "note": "",
    },
    {
        "title": "Programar con Inteligencia Artificial",
        "url": "https://amzn.eu/d/eK4f73N",
        "note": "",
    },
    {
        "title": "Del vibe coding al Spec-Driven Development",
        "url": "",
        "note": "próximamente",
    },
]

# One-line credit for the terminal.
TERMINAL_CREDIT = f"SpecJudge by {AUTHOR} · {SITE} · {YOUTUBE}"
