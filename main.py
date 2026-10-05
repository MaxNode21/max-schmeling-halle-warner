import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup


KANAL_NAME = os.getenv("NTFY_TOPIC", "max-schmeling-halle-warner")
URL = "https://www.max-schmeling-halle.de/events"
BERLIN = ZoneInfo("Europe/Berlin")

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

EVENT_RE = re.compile(
    rf"{WOCHENTAGE_PATTERN}\s*,?\s*"
    rf"(?P<day>\d{{1,2}})\.?\s+"
    rf"(?P<month>{MONATE_PATTERN})\s+"
    rf"'?(?P<year>\d{{2}}|\d{{4}})\s+"
    rf"(?P<time>\d{{1,2}}:\d{{2}})\s*Uhr",
    re.IGNORECASE,
)

TRAILING_STATUS_RE = re.compile(
    r"\s+(?:Im Vorverkauf erhältlich|ausverkauft)\s+(?:Tickets|Infos)\s*$",
    re.IGNORECASE,
)


def send_notification(title, body, click_url=URL):
    response = requests.post(
        "https://ntfy.sh/",
        json={
            "topic": KANAL_NAME,
            "message": body,
            "title": title,
            "priority": 4,
            "tags": ["ticket"],
            "click": click_url,
        },
        timeout=15,
    )
    response.raise_for_status()


def categorize_event(title):
    text = title.lower()

    if any(
        word in text
        for word in (
            " vs.",
            "füchse",
            "handball",
            "volleys",
            "alba berlin",
            "volleyball",
            "basketball",
        )
    ):
        return f"Sport: {title}"

    if any(word in text for word in ("tour", "live", "konzert")):
        return f"Konzert: {title}"

    return f"Event: {title}"


def clean_event_title(text):
    title = TRAILING_STATUS_RE.sub("", text).strip()
    title = re.sub(
        r"\s+(?:Tickets|Infos)\s*$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()
    return title or "Veranstaltung"


def extract_events(html):
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()

    for link in soup.find_all("a", href=True):
        text = " ".join(link.stripped_strings)
        match = EVENT_RE.search(text)

        if not match:
            continue

        month_name = match.group("month").lower()
        month = MONATE[month_name]

        year_value = int(match.group("year"))
        year = year_value if year_value >= 100 else 2000 + year_value

        day = int(match.group("day"))
        start_time = match.group("time")
        event_date = datetime(year, month, day, tzinfo=BERLIN).date()
        title = clean_event_title(text[match.end():])

        event_id = (event_date.isoformat(), start_time, title)
        if event_id in seen:
            continue

        seen.add(event_id)
        events.append(
            {
                "date": event_date,
                "time": start_time,
                "title": title,
                "url": requests.compat.urljoin(URL, link.get("href")),
            }
        )

    return events


def fetch_events():
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/130 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        }
    )

    response = session.get(URL, timeout=20)
    response.raise_for_status()

    events = extract_events(response.text)

    # Die Eventseite enthält normalerweise viele zukünftige Termine.
    # Falls gar nichts erkannt wird, ist eher der Seitenaufbau geändert worden
    # als dass tatsächlich kein einziges Event existiert.
    if not events:
        raise RuntimeError(
            "Keine Veranstaltungen auf der Eventseite erkannt. "
            "Möglicherweise hat sich das Webseitenformat geändert."
        )

    return events


def check_events():
    today = datetime.now(BERLIN).date()

    print(f"Starte Event-Check für {today:%d.%m.%Y} ...")
    print(f"Rufe {URL} ab ...")

    events = fetch_events()
    print(f"{len(events)} Veranstaltungstermine erkannt.")

    todays_events = [event for event in events if event["date"] == today]

    if not todays_events:
        print(f"Heute ({today:%d.%m.%Y}) keine Veranstaltungen gefunden.")
        return

    for event in todays_events:
        title = categorize_event(event["title"])
        body = (
            f"📅 Heute: {event['date']:%d.%m.%Y}\n"
            f"🎬 Beginn: {event['time']} Uhr\n"
            f"🔗 {event['url']}"
        )

        print(f"Sende Push für: {title}")
        send_notification(title, body, event["url"])


def main():
    try:
        if "--test" in sys.argv:
            print("Sende Test-Nachricht ...")
            send_notification(
                "Test: Max-Schmeling-Halle",
                "✅ Der Max-Schmeling-Halle-Warner funktioniert.",
            )
            print("Test-Nachricht wurde gesendet.")
            return

        check_events()

    except Exception as exc:
        print(f"Fehler: {type(exc).__name__}: {exc}")

        try:
            send_notification(
                "Max-Schmeling-Halle: Skriptfehler",
                f"{type(exc).__name__}: {exc}",
            )
        except Exception as notification_exc:
            print(
                "Fehler-Nachricht konnte nicht gesendet werden:",
                notification_exc,
            )

        raise


if __name__ == "__main__":
    main()
