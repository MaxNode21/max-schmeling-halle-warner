"""Max-Schmeling-Halle-Warner.

Prüft jeden Morgen die Eventseite der Max-Schmeling-Halle und schickt über
ntfy eine Push-Nachricht, wenn dort heute eine Veranstaltung stattfindet.

    python main.py                               # Check für heute
    python main.py --test                        # nur Test-Nachricht senden
    python main.py --dry-run                     # nichts senden, nur anzeigen
    python main.py --dry-run --datum 2026-11-14  # anderen Tag prüfen
"""

import argparse
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URL = "https://www.max-schmeling-halle.de/events"
NTFY_URL = "https://ntfy.sh/"
BERLIN = ZoneInfo("Europe/Berlin")

# Nur die Notlösung, falls das Secret NTFY_TOPIC fehlt. ntfy-Kanäle sind
# öffentlich: Wer den Namen kennt (und der steht hier im öffentlichen Repo),
# kann mitlesen und dir selbst Nachrichten aufs Handy schicken.
STANDARD_KANAL = "max-schmeling-halle-warner"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/130 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

MONATE = {
    "jan": 1,
    "januar": 1,
    "feb": 2,
    "februar": 2,
    "mär": 3,
    "märz": 3,
    "mrz": 3,
    "apr": 4,
    "april": 4,
    "mai": 5,
    "jun": 6,
    "juni": 6,
    "jul": 7,
    "juli": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "okt": 10,
    "oktober": 10,
    "nov": 11,
    "november": 11,
    "dez": 12,
    "dezember": 12,
}

WOCHENTAGE_PATTERN = (
    r"(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag|"
    r"Mo\.?|Di\.?|Mi\.?|Do\.?|Fr\.?|Sa\.?|So\.?)"
)

MONATE_PATTERN = "|".join(
    sorted((re.escape(monat) for monat in MONATE), key=len, reverse=True)
)

# Erkennt z. B. "Sa., 14. Nov '26 15:55 Uhr". Etwas tolerant gegenüber
# kleinen Formatänderungen: "Nov." mit Punkt, ’ statt ', "19.30 Uhr",
# Komma oder Strich zwischen Jahr und Uhrzeit.
EVENT_RE = re.compile(
    rf"{WOCHENTAGE_PATTERN}\s*,?\s*"
    rf"(?P<day>\d{{1,2}})\.?\s+"
    rf"(?P<month>{MONATE_PATTERN})\.?\s+"
    rf"['’]?(?P<year>\d{{4}}|\d{{2}})[\s,|–-]+"
    rf"(?P<time>\d{{1,2}}[:.]\d{{2}})\s*Uhr",
    re.IGNORECASE,
)

# Status- und Button-Texte, die auf der Eventseite hinter dem Titel stehen.
TRAILING_RE = re.compile(
    r"\s*(?:\bTickets|\bInfos?|\b(?:demnächst )?im Vorverkauf(?: erhältlich)?"
    r"|\bausverkauft|\babgesagt|\bverschoben|\bverlegt|\bentfällt)\s*$",
    re.IGNORECASE,
)

# Hinweise darauf, dass die Veranstaltung womöglich gar nicht stattfindet.
STATUS_RE = re.compile(r"\b(abgesagt|verschoben|verlegt|entfällt)\b", re.IGNORECASE)

# Kurze, mehrdeutige Wörter nur als ganzes Wort bzw. am Wortende, damit z. B.
# "Oliver" nicht als "live" und "Tournament" nicht als "tour" zählt.
# Zusammensetzungen wie "Weihnachtskonzert" oder "Abschiedstour" passen trotzdem.
SPORT_RE = re.compile(
    r"\bvs\b|füchse|volleys|\balba\b|handball|volleyball|basketball|globetrotters"
    r"|bundesliga|champions league|pokal|turnier|box(?:en|ing|gala|kampf)|darts",
    re.IGNORECASE,
)
KONZERT_RE = re.compile(r"konzert|tournee|tour\b|\blive\b|unplugged", re.IGNORECASE)


@dataclass(frozen=True)
class Event:
    day: date
    start: str  # "HH:MM"
    title: str
    url: str
    status: str | None = None  # z. B. "abgesagt", falls die Website das meldet


@dataclass(frozen=True)
class Notification:
    title: str
    body: str
    click: str = URL
    priority: int = 4
    tags: tuple[str, ...] = ("ticket",)


# --- HTTP und ntfy ---------------------------------------------------------


def create_session():
    """HTTP-Session, die kurze Aussetzer (Timeouts, 5xx, 429) selbst überbrückt."""
    retry = Retry(
        total=3,
        backoff_factor=2,  # Pausen zwischen den Versuchen: 0 s, 4 s, 8 s
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        respect_retry_after_header=False,  # kein minutenlanges Warten im Workflow
        raise_on_status=False,  # am Ende normale HTTPError statt RetryError
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def ntfy_topic():
    return os.getenv("NTFY_TOPIC", "").strip() or STANDARD_KANAL


def send_notification(session, notification):
    response = session.post(
        NTFY_URL,
        json={
            "topic": ntfy_topic(),
            "title": notification.title,
            "message": notification.body,
            "priority": notification.priority,
            "tags": list(notification.tags),
            "click": notification.click,
        },
        timeout=15,
    )
    response.raise_for_status()


def show_notification(notification):
    print(f"[Trockenlauf] Würde senden: {notification.title}")
    for line in notification.body.splitlines():
        print(f"    {line}")


def github_run_url():
    """Link zum aktuellen Actions-Lauf: Die Fehler-Push führt so direkt ins Log."""
    server = os.getenv("GITHUB_SERVER_URL")
    repo = os.getenv("GITHUB_REPOSITORY")
    run_id = os.getenv("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return URL


# --- Eventseite auslesen ---------------------------------------------------


def categorize_event(title):
    if SPORT_RE.search(title):
        return f"Sport: {title}"
    if KONZERT_RE.search(title):
        return f"Konzert: {title}"
    return f"Event: {title}"


def clean_event_title(text):
    title = " ".join(text.split())
    while True:
        shorter = TRAILING_RE.sub("", title)
        if shorter == title:
            break
        title = shorter
    return title.strip(" ,|–-") or "Veranstaltung"


def parse_event_date(match):
    """Datum aus dem Treffer, None bei unmöglichen Daten wie dem 31. Februar."""
    year = int(match.group("year"))
    if year < 100:
        year += 2000
    month = MONATE[match.group("month").lower()]
    try:
        return date(year, month, int(match.group("day")))
    except ValueError:
        return None


def parse_start_time(value):
    hours, minutes = re.split(r"[:.]", value)
    return f"{int(hours):02d}:{minutes}"


def extract_events(html, base_url=URL):
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()

    # Jede Veranstaltung ist auf der Eventseite ein eigener Link, der Datum,
    # Uhrzeit und Titel enthält. So bleibt die Zuordnung stabil.
    for link in soup.find_all("a", href=True):
        text = " ".join(link.stripped_strings)
        match = EVENT_RE.search(text)
        if not match:
            continue

        event_day = parse_event_date(match)
        if event_day is None:
            print(f"Warnung: Termin mit ungültigem Datum übersprungen: {text!r}")
            continue

        rest = text[match.end() :]
        status = STATUS_RE.search(rest)
        event = Event(
            day=event_day,
            start=parse_start_time(match.group("time")),
            title=clean_event_title(rest),
            url=urljoin(base_url, link["href"]),
            status=status.group(1).lower() if status else None,
        )

        key = (event.day, event.start, event.title)
        if key in seen:
            continue
        seen.add(key)
        events.append(event)

    return events


def fetch_events(session):
    response = session.get(URL, headers=BROWSER_HEADERS, timeout=20)
    response.raise_for_status()

    # Bytes statt response.text: Ohne charset im HTTP-Header nimmt requests
    # ISO-8859-1 an und macht aus "März" Zeichensalat. BeautifulSoup liest die
    # Kodierung dagegen aus dem <meta>-Tag der Seite.
    events = extract_events(response.content, response.url)

    # Die Eventseite enthält normalerweise viele zukünftige Termine.
    # Falls gar nichts erkannt wird, ist eher der Seitenaufbau geändert worden
    # als dass tatsächlich kein einziges Event existiert.
    if not events:
        raise RuntimeError(
            "Keine Veranstaltungen auf der Eventseite erkannt. "
            "Möglicherweise hat sich das Webseitenformat geändert."
        )

    return events


# --- Nachrichten bauen -----------------------------------------------------


def group_events(events):
    """Fasst mehrere Vorstellungen derselben Veranstaltung am selben Tag zusammen."""
    groups = {}
    for event in sorted(events, key=lambda e: (e.day, e.start)):
        groups.setdefault((event.day, event.title), []).append(event)
    return list(groups.values())


def start_times(group):
    return " & ".join(event.start for event in group)


def status_hints(group):
    return sorted({event.status for event in group if event.status})


def build_day_notifications(events, day, today):
    notifications = []

    for group in group_events(e for e in events if e.day == day):
        first = group[0]
        title = categorize_event(first.title)
        lines = [
            f"📅 Heute: {day:%d.%m.%Y}" if day == today else f"📅 {day:%d.%m.%Y}",
            f"🎬 Beginn: {start_times(group)} Uhr",
        ]

        hints = status_hints(group)
        if hints:
            title = f"⚠️ {title}"
            lines.append(f"⚠️ Laut Website: {', '.join(hints)}")

        lines.append(f"🔗 {first.url}")
        notifications.append(Notification(title, "\n".join(lines), click=first.url))

    return notifications


# --- Ablauf ----------------------------------------------------------------


def check_events(day, session, notify, today):
    print(f"Starte Event-Check für {day:%d.%m.%Y} ...")
    print(f"Rufe {URL} ab ...")

    events = fetch_events(session)
    print(f"{len(events)} Veranstaltungstermine erkannt:")
    for event in sorted(events, key=lambda e: (e.day, e.start)):
        status = f" [{event.status}]" if event.status else ""
        print(f"  {event.day:%d.%m.%Y} {event.start}  {event.title}{status}")

    notifications = build_day_notifications(events, day, today)
    if not notifications:
        print(f"Am {day:%d.%m.%Y} keine Veranstaltungen gefunden.")

    for notification in notifications:
        notify(notification)


def parse_date_argument(value):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"ungültiges Datum {value!r}, erwartet JJJJ-MM-TT"
        ) from None


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Push-Warnung bei Veranstaltungen in der Max-Schmeling-Halle."
    )
    parser.add_argument(
        "--test", action="store_true", help="nur eine Test-Nachricht senden"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="nichts senden, nur anzeigen, was gesendet würde",
    )
    parser.add_argument(
        "--datum",
        type=parse_date_argument,
        metavar="JJJJ-MM-TT",
        help="dieses Datum statt heute prüfen",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    session = create_session()

    def notify(notification):
        if args.dry_run:
            show_notification(notification)
        else:
            print(f"Sende Push: {notification.title}")
            send_notification(session, notification)

    if ntfy_topic() == STANDARD_KANAL:
        # Erscheint in GitHub Actions als gelbe Warnung in der Lauf-Übersicht.
        print(
            "::warning::Secret NTFY_TOPIC ist nicht gesetzt, es wird der "
            f"öffentliche Kanal '{STANDARD_KANAL}' benutzt. Siehe README."
        )

    try:
        if args.test:
            notify(
                Notification(
                    "Test: Max-Schmeling-Halle",
                    "✅ Der Max-Schmeling-Halle-Warner funktioniert.",
                )
            )
            return

        today = datetime.now(BERLIN).date()
        check_events(args.datum or today, session, notify, today)

    except Exception as exc:
        print(f"Fehler: {type(exc).__name__}: {exc}")

        try:
            notify(
                Notification(
                    "Max-Schmeling-Halle: Skriptfehler",
                    f"{type(exc).__name__}: {exc}"[:500],
                    click=github_run_url(),
                    tags=("warning",),
                )
            )
        except Exception as notification_exc:
            print(
                "Fehler-Nachricht konnte nicht gesendet werden:",
                notification_exc,
            )

        raise


if __name__ == "__main__":
    main()
