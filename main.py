import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import time

# --- DEIN KANAL ---
KANAL_NAME = "max-schmeling-halle-warner"
# ------------------

def get_today_date_strings():
    """Gibt das heutige Datum in verschiedenen Formaten zurück"""
    heute = datetime.now()
    monate = {
        1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
        7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
    }
    return [
        heute.strftime("%d.%m.%Y"),         # 16.02.2026
        f"{heute.day}. {monate[heute.month]}" # 16. Februar
    ]

def parse_time(text):
    """Sucht nach einer Uhrzeit im Text (HH:MM)"""
    match = re.search(r"(\d{1,2}:\d{2})", text)
    if match:
        return match.group(1)
    return None

def check_events():
    url = "https://www.max-schmeling-halle.de/events-tickets"
    print(f"--- Prüfe {url} ---")
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Wir suchen nach Containern, die Events sein könnten.
        # Da wir die genaue Klasse nicht kennen, suchen wir nach dem Datum
        # und gehen dann zum "Eltern-Element" hoch.
        
        datums_formate = get_today_date_strings()
        gefundene_events_hashes = set() # Um Doppelte zu vermeiden

        found_something = False

        for datum_str in datums_formate:
            # Finde alle Textelemente, die das Datum enthalten
            for element in soup.find_all(string=re.compile(re.escape(datum_str))):
                
                # Wir klettern im HTML-Baum hoch, um den ganzen Event-Kasten zu finden
                # Meistens ist es ein <div> oder <a> oder <article>
                container = element.find_parent("div") 
                if not container:
                    continue
                
                text_block = container.get_text(" ", strip=True)
                
                # 1. TITEL FINDEN
                # Wir suchen nach Überschriften im Container (h2, h3, h4)
                titel_tag = container.find(['h2', 'h3', 'h4', 'strong'])
                if titel_tag:
                    titel = titel_tag.get_text(strip=True)
                else:
                    # Fallback: Die ersten 40 Zeichen des Containers
                    titel = text_block[:40] + "..."

                # 2. UHRZEITEN FINDEN
                einlass = "17:00" # Fallback, falls nichts gefunden wird
                beginn = "19:00"
                
                # Suche nach "Einlass" im Text
                einlass_match = re.search(r"Einlass.*?(\d{1,2}:\d{2})", text_block, re.IGNORECASE)
                if einlass_match:
                    einlass = einlass_match.group(1)
                
                beginn_match = re.search(r"Beginn.*?(\d{1,2}:\d{2})", text_block, re.IGNORECASE)
                if beginn_match:
                    beginn = beginn_match.group(1)

                # Doppelungen vermeiden (gleicher Titel + gleiche Zeit)
                event_hash = f"{titel}-{einlass}"
                if event_hash in gefundene_events_hashes:
                    continue
                gefundene_events_hashes.add(event_hash)
                found_something = True

                print(f"Gefunden: {titel} (Einlass: {einlass})")

                # 3. VERZÖGERUNG BERECHNEN (2 Stunden vor Einlass)
                # Wir bauen ein echtes Zeit-Objekt für heute
                heute_str = datetime.now().strftime("%Y-%m-%d")
                einlass_dt = datetime.strptime(f"{heute_str} {einlass}", "%Y-%m-%d %H:%M")
                
                # Alarm-Zeit = Einlass - 2 Stunden
                alarm_zeit = einlass_dt - timedelta(hours=2)
                
                # Umrechnen in Unix Timestamp für ntfy
                timestamp = int(alarm_zeit.timestamp())
                
                # Falls der Alarm in der Vergangenheit wäre (z.B. Skript läuft erst um 9, Einlass war 8),
                # senden wir sofort (kein Delay).
                jetzt = int(time.time())
                delay_header = str(timestamp)
                if timestamp < jetzt:
                    print("  -> Zeit schon vorbei, sende sofort.")
                    delay_header = "" # Leer lassen = sofort senden

                # 4. NACHRICHT SENDEN
                nachricht = f"Bald geht's los: {titel}\nEinlass: {einlass} Uhr\nBeginn: {beginn} Uhr"
                
                print(f"  -> Plane Benachrichtigung für {alarm_zeit.strftime('%H:%M')} Uhr")
                
                requests.post(
                    f"https://ntfy.sh/{KANAL_NAME}",
                    data=nachricht.encode('utf-8'),
                    headers={
                        "Title": f"Heute: {titel} 🎤",
                        "Priority": "high",
                        "Tags": "ticket,music",
                        "Delay": delay_header  # <--- HIER IST DER TRICK!
                    }
                )

        if not found_something:
            print("Heute keine Events gefunden.")

    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    check_events()
