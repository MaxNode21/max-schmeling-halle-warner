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

    # Flexibles Datum für HEUTE berechnen
    heute = datetime.now()
    tag = heute.day
    jahr = heute.year
    jahr_kurz = heute.strftime("%y")
    
    # Deutsche Monatsnamen für das Suchmuster
    monate = ["", "Januar", "Februar", "März", "April", "Mai", "Juni", 
              "Juli", "August", "September", "Oktober", "November", "Dezember"]
    monate_kurz = ["", "Jan", "Feb", "Mär", "Apr", "Mai", "Jun", 
                   "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
    
    monat_name = monate[heute.month]
    monat_kurz = monate_kurz[heute.month]
    monat_zahl = heute.month
    
    # Baut ein flexibles Suchmuster für "Heute" (z.B. "09.03.2026", "9. März 2026", "09 Mär 26", "09.03.")
    regex_heute = rf"0?{tag}\.?\s*(?:0?{monat_zahl}|{monat_name}|{monat_kurz})\.?\s*(?:{jahr}|{jahr_kurz})?"

    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9",
        })

        # Seite abrufen
        response = session.get(URL, timeout=15)

        if response.status_code != 200:
            raise Exception(f"HTTP Fehler {response.status_code}")

        # Text aus der Webseite extrahieren
        soup = BeautifulSoup(response.text, "html.parser")
        full_text = soup.get_text(" | ", strip=True)

        events_found = False
        sent_hashes = set()

        # Wir suchen jetzt flexibel nach dem heutigen Datum im Text
        for match in re.finditer(regex_heute, full_text, re.IGNORECASE):
            datum_str = match.group().strip()
            
            # Falls das Datum am Ende einen überflüssigen Punkt oder Leerzeichen hat
            if datum_str.endswith('.') and not datum_str[-2].isdigit():
                datum_str = datum_str[:-1].strip()

            found_idx = match.start()
            # Wir schneiden großzügig Text rund um das gefundene Datum aus
            start_pos = max(0, found_idx - 300)
            end_pos = min(len(full_text), found_idx + 500)
            ausschnitt = full_text[start_pos:end_pos]

            # Einlass suchen
            e_match = re.search(r"Einlass.*?(\d{1,2}[:.]\d{2})", ausschnitt, re.IGNORECASE)
            einlass = e_match.group(1).replace(".", ":") if e_match else "Unbekannt"

            # Beginn suchen
            b_match = re.search(r"Beginn.*?(\d{1,2}[:.]\d{2})", ausschnitt, re.IGNORECASE)
            beginn = b_match.group(1).replace(".", ":") if b_match else "Unbekannt"

            # Titel finden (Textteil direkt vor dem Datum)
            parts = ausschnitt.split(datum_str)
            titel = "Event"

            if len(parts) > 0:
                text_davor = parts[0]
                titel_teile = text_davor.split("|")

                for teil in reversed(titel_teile):
                    teil = teil.strip()

                    # Wir filtern nutzlose Wörter aus, um den echten Event-Namen zu finden
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

            # Doppelte Push-Nachrichten für dasselbe Event am selben Tag vermeiden
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
            print(f"Heute ({tag}. {monat_name}) keine Veranstaltungen gefunden.")

    except Exception as e:
        print(f"Fehler: {e}")
        send_notification("Skript Error", str(e))

if __name__ == "__main__":
    check_events()
