import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import pytz # Für korrekte Zeitzonen

# --- KONFIGURATION ---
KANAL_NAME = "max-schmeling-halle-warner"
TEST_MODUS = True  # <--- HIER: Zuerst auf True lassen, um den TITEL zu prüfen!
                   # Wenn der Titel stimmt, stell es auf False.
# ---------------------

def check_events():
    url = "https://www.max-schmeling-halle.de/events-tickets"
    print(f"--- Prüfe {url} ---")

    # Zeitzone Berlin definieren (wichtig für den Timer!)
    berlin_tz = pytz.timezone('Europe/Berlin')
    heute = datetime.now(berlin_tz)
    
    # Datumstexte erstellen (z.B. "16.02.2026" und "16. Februar")
    monate = {
        1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
        7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
    }
    datum_kurz = heute.strftime("%d.%m.%Y")
    datum_lang = f"{heute.day}. {monate[heute.month]}"
    such_datums = [datum_kurz, datum_lang]

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        gefunden = False
        gefundene_hashes = set()

        # Wir suchen gezielt nach HTML-Elementen, die das Datum enthalten
        for datum_str in such_datums:
            # Finde alle Texte, die das Datum enthalten
            for element in soup.find_all(string=re.compile(re.escape(datum_str))):
                
                # Jetzt klettern wir im HTML nach oben, um den "Kasten" des Events zu finden
                # Wir gehen maximal 4 Ebenen hoch, bis wir einen "div" oder "article" finden
                container = element.parent
                for _ in range(3):
                    if container.name in ['div', 'article', 'li']:
                        break
                    container = container.parent
                
                if not container:
                    continue

                # --- 1. TITEL FINDEN ---
                # Wir suchen im Container nach Überschriften (h2, h3, h4 oder Links mit Titel)
                titel = "Unbekanntes Event"
                header_tag = container.find(['h2', 'h3', 'h4', 'strong'])
                
                if header_tag:
                    titel = header_tag.get_text(strip=True)
                else:
                    # Fallback: Suche nach Links, die oft den Titel haben
                    link_tag = container.find('a')
                    if link_tag and len(link_tag.get_text(strip=True)) > 5:
                        titel = link_tag.get_text(strip=True)

                # --- 2. UHRZEITEN FINDEN ---
                text_inhalt = container.get_text(" ", strip=True)
                
                einlass = "??"
                beginn = "??"

                einlass_match = re.search(r"Einlass.*?(\d{1,2}:\d{2})", text_inhalt, re.IGNORECASE)
                if einlass_match: einlass = einlass_match.group(1)

                beginn_match = re.search(r"Beginn.*?(\d{1,2}:\d{2})", text_inhalt, re.IGNORECASE)
                if beginn_match: beginn = beginn_match.group(1)

                # Doppelte verhindern
                event_hash = f"{titel}-{einlass}"
                if event_hash in gefundene_hashes:
                    continue
                gefundene_hashes.add(event_hash)
                gefunden = True

                print(f"Gefunden: '{titel}' (Start: {beginn}, Einlass: {einlass})")

                # --- 3. VERZÖGERUNG BERECHNEN ---
                delay_header = ""
                
                if TEST_MODUS:
                    print("  -> TEST-MODUS: Sende sofort.")
                elif einlass != "??":
                    # Zeitrechnung: Wann ist Einlass heute?
                    uhr_h, uhr_m = map(int, einlass.split(':'))
                    event_zeit = heute.replace(hour=uhr_h, minute=uhr_m, second=0, microsecond=0)
                    
                    # Alarm soll 2 Stunden (120 Min) vorher sein
                    alarm_zeit = event_zeit - timedelta(minutes=120)
                    
                    # Differenz von JETZT bis ALARM berechnen
                    differenz = alarm_zeit - datetime.now(berlin_tz)
                    minuten_warten = int(differenz.total_seconds() / 60)

                    if minuten_warten > 0:
                        delay_header = f"{minuten_warten}m" # z.B. "480m" an ntfy senden
                        print(f"  -> Verzögerung: {delay_header} (Alarm um {alarm_zeit.strftime('%H:%M')})")
                    else:
                        print("  -> Alarmzeit schon vorbei, sende sofort.")

                # --- 4. NACHRICHT SENDEN ---
                requests.post(
                    f"https://ntfy.sh/{KANAL_NAME}",
                    data=f"Bald geht's los: {titel} 🎤\nEinlass: {einlass} Uhr\nBeginn: {beginn} Uhr".encode('utf-8'),
                    headers={
                        "Title": f"Heute: {titel}",
                        "Priority": "high",
                        "Tags": "ticket,music",
                        "Delay": delay_header
                    }
                )

        if not gefunden:
            print(f"Keine Events für heute ({datum_kurz}) gefunden.")
            if TEST_MODUS:
                requests.post(f"https://ntfy.sh/{KANAL_NAME}", data="Test OK: Skript läuft, kein Event gefunden.".encode('utf-8'), headers={"Title": "Skript Test"})

    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    check_events()
