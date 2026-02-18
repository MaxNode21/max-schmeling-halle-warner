import requests
from bs4 import BeautifulSoup
from datetime import datetime
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
    print("Starte Morgen-Check...")

    heute = datetime.now().strftime("%d.%m.%Y")

    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9",
        })

        response = session.get(URL, timeout=15)

        if response.status_code != 200:
            raise Exception(f"HTTP Fehler {response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")
        full_text = soup.get_text(" | ", strip=True)

        events_found = False
        sent_hashes = set()

        for match in re.finditer(r"\d{2}\.\d{2}\.\d{4}", full_text):

            datum_str = match.group()

            if datum_str != heute:
                continue

            found_idx = match.start()
            start_pos = max(0, found_idx - 300)
            end_pos = min(len(full_text), found_idx + 500)
            ausschnitt = full_text[start_pos:end_pos]

            # Einlass suchen
            e_match = re.search(r"Einlass.*?(\d{1,2}[:.]\d{2})", ausschnitt, re.IGNORECASE)
            einlass = e_match.group(1).replace(".", ":") if e_match else "Unbekannt"

            # Beginn suchen
            b_match = re.search(r"Beginn.*?(\d{1,2}[:.]\d{2})", ausschnitt, re.IGNORECASE)
            beginn = b_match.group(1).replace(".", ":") if b_match else "Unbekannt"

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

            hash_id = f"{titel}-{beginn}"
            if hash_id in sent_hashes:
                continue

            sent_hashes.add(hash_id)
            events_found = True

            body = (
                f"📅 Heute: {datum_str}\n"
                f"🚪 Einlass: {einlass} Uhr\n"
                f"🎬 Beginn: {beginn} Uhr"
            )

            print(f"Sende Push für: {titel}")
            send_notification(titel, body)

        if not events_found:
            print("Heute keine Veranstaltungen.")

    except Exception as e:
        print(f"Fehler: {e}")
        send_notification("Skript Error", str(e))


if __name__ == "__main__":
    check_events()
