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


def check_events():
    print(f"Prüfe {URL}")

    heute = datetime.now()
    datum_kurz = heute.strftime("%d.%m.%Y")

    monate = {
        1: "Januar", 2: "Februar", 3: "März", 4: "April",
        5: "Mai", 6: "Juni", 7: "Juli", 8: "August",
        9: "September", 10: "Oktober",
        11: "November", 12: "Dezember"
    }

    datum_text = f"{int(heute.strftime('%d'))}. {monate[heute.month]}"

    try:
        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.get(URL, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        full_text = soup.get_text(" | ", strip=True)

        gefunden = False
        gefundene_hashes = set()

        for date_pattern in [datum_kurz, datum_text]:
            for match in re.finditer(re.escape(date_pattern), full_text):

                found_idx = match.start()

                start_pos = max(0, found_idx - 300)
                end_pos = min(len(full_text), found_idx + 500)
                ausschnitt = full_text[start_pos:end_pos]

                # Zeiten suchen
                einlass = "?"
                beginn = "?"

                e_match = re.search(r"Einlass.*?(\d{1,2}[:.]\d{2})", ausschnitt, re.IGNORECASE)
                if e_match:
                    einlass = e_match.group(1).replace(".", ":")

                b_match = re.search(r"Beginn.*?(\d{1,2}[:.]\d{2})", ausschnitt, re.IGNORECASE)
                if b_match:
                    beginn = b_match.group(1).replace(".", ":")

                # Titel finden
                parts = ausschnitt.split(date_pattern)
                titel = "Event heute"

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

                if len(titel) > 80:
                    titel = titel[:77] + "..."

                # Handball erkennen
                if "vs" in titel or "Füchse" in titel:
                    titel = f"Handball: {titel}"
                else:
                    titel = f"Konzert/Event: {titel}"

                hash_id = f"{titel}-{beginn}"
                if hash_id in gefundene_hashes:
                    continue

                gefundene_hashes.add(hash_id)
                gefunden = True

                print(f"Gefunden: {titel} ({beginn})")

                body = f"Einlass: {einlass} Uhr\nBeginn: {beginn} Uhr"

                send_notification(titel, body)

        if not gefunden:
            print("Heute kein Event gefunden.")

    except Exception as e:
        print(f"Fehler: {e}")
        send_notification("Skript Error", str(e))


if __name__ == "__main__":
    check_events()
