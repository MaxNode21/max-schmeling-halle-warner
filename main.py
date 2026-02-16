import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re

KANAL_NAME = "max-schmeling-halle-warner"
URL = "https://www.max-schmeling-halle.de/events-tickets"


def send_notification(title, body):
    requests.post(
        f"https://ntfy.sh/{KANAL_NAME}",
        data=body.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": "high",
            "Tags": "ticket",
            "Click": URL
        }
    )


def categorize_event(titel):
    t = titel.lower()

    if any(w in t for w in ["vs", "füchse", "handball", "spiel"]):
        return f"Sport: {titel}"
    elif any(w in t for w in ["tour", "live", "konzert"]):
        return f"Konzert: {titel}"
    else:
        return f"Event: {titel}"


def check_events():
    print("Starte Prüfung...")

    now = datetime.now()

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(URL, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        full_text = soup.get_text(" | ", strip=True)

        events_checked = set()

        # Suche nach allen Datumsangaben im Format DD.MM.YYYY
        date_matches = re.finditer(r"\d{2}\.\d{2}\.\d{4}", full_text)

        for match in date_matches:
            datum_str = match.group()

            try:
                event_date = datetime.strptime(datum_str, "%d.%m.%Y")
            except:
                continue

            found_idx = match.start()
            start_pos = max(0, found_idx - 300)
            end_pos = min(len(full_text), found_idx + 500)
            ausschnitt = full_text[start_pos:end_pos]

            # Einlasszeit suchen
            e_match = re.search(r"Einlass.*?(\d{1,2}[:.]\d{2})", ausschnitt, re.IGNORECASE)
            if not e_match:
                continue

            einlass_str = e_match.group(1).replace(".", ":")

            try:
                einlass_time = datetime.strptime(einlass_str, "%H:%M").time()
            except:
                continue

            # Kombiniere Datum + Einlasszeit
            event_datetime = datetime.combine(event_date.date(), einlass_time)

            reminder_time = event_datetime - timedelta(hours=2)

            # Nur wenn jetzt im 15-Minuten-Fenster
            if reminder_time <= now <= reminder_time + timedelta(minutes=15):

                # Titel finden
                parts = ausschnitt.split(datum_str)
                titel = "Event"

                if len(parts) > 0:
                    text_davor = parts[0]
                    titel_teile = text_davor.split("|")

                    for teil in reversed(titel_teile):
                        teil = teil.strip()
                        if (
                            len(teil) > 5 and
                            not any(w in teil for w in [
                                "Montag", "Dienstag", "Mittwoch",
                                "Donnerstag", "Freitag",
                                "Samstag", "Sonntag",
                                "Tickets", "Infos", "Details"
                            ])
                        ):
                            titel = teil
                            break

                titel = categorize_event(titel)

                hash_id = f"{titel}-{event_datetime}"

                if hash_id in events_checked:
                    continue

                events_checked.add(hash_id)

                body = (
                    f"📅 Datum: {event_datetime.strftime('%d.%m.%Y')}\n"
                    f"🚪 Einlass: {einlass_str} Uhr\n"
                    f"⏰ Beginn in 2 Stunden!"
                )

                print(f"Sende Erinnerung für: {titel}")
                send_notification(titel, body)

    except Exception as e:
        print(f"Fehler: {e}")
        send_notification("Skript Error", str(e))


if __name__ == "__main__":
    check_events()
