import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

# --- KONFIGURATION ---
KANAL_NAME = "max-schmeling-halle-warner"
# ---------------------

def check_events():
    url = "https://www.max-schmeling-halle.de/events-tickets"
    print(f"--- Prüfe {url} ---")
    
    # 1. Datum definieren
    heute = datetime.now()
    monate = {1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
              7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"}
    
    datum_kurz = heute.strftime("%d.%m.%Y")       # 16.02.2026
    datum_text = f"{int(heute.strftime('%d'))}. {monate[heute.month]}" # 16. Februar
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        
        # WICHTIG: Wir nutzen " | " als Trenner. Das hat beim Titel geholfen!
        soup = BeautifulSoup(response.text, 'html.parser')
        full_text = soup.get_text(" | ", strip=True)

        gefunden = False
        gefundene_hashes = set()
        
        # Wir suchen nach dem Datum im Text
        # Wir nehmen das Datum, das zuerst gefunden wird.
        for match in re.finditer(re.escape(datum_kurz), full_text):
            found_idx = match.start()
            
            # 2. Großzügigen Text-Ausschnitt holen (damit finden wir auch die Zeiten wieder!)
            # Wir schauen 300 Zeichen zurück (Titel) und 500 Zeichen vor (Zeiten)
            start_pos = max(0, found_idx - 300)
            end_pos = min(len(full_text), found_idx + 500)
            ausschnitt = full_text[start_pos:end_pos]
            
            # --- TEIL A: ZEITEN FINDEN (Wie um 22:10 Uhr) ---
            einlass = "??"
            beginn = "??"
            
            # Robuste Suche nach Uhrzeiten
            e_match = re.search(r"Einlass.*?(\d{1,2}[:.]\d{2})", ausschnitt, re.IGNORECASE)
            if e_match: einlass = e_match.group(1).replace('.', ':')
            
            b_match = re.search(r"Beginn.*?(\d{1,2}[:.]\d{2})", ausschnitt, re.IGNORECASE)
            if b_match: beginn = b_match.group(1).replace('.', ':')

            # --- TEIL B: TITEL FINDEN (Wie um 22:17 Uhr) ---
            # Wir schneiden alles ab dem Datum ab. Der Titel steht davor.
            parts = ausschnitt.split(datum_kurz)
            if len(parts) > 0:
                text_davor = parts[0]
                titel_teile = text_davor.split("|")
                
                # Wir suchen rückwärts nach dem Titel
                titel = "Event heute"
                for teil in reversed(titel_teile):
                    teil = teil.strip()
                    # Filter: Ignoriere Wochentage oder leeres Zeug
                    if len(teil) > 3 and "Montag" not in teil and "Dienstag" not in teil and "Mittwoch" not in teil:
                        titel = teil
                        break
                
                # Kürzen, falls viel zu lang
                if len(titel) > 60: titel = titel[:57] + "..."
            else:
                titel = "Event heute"

            # Check: Doppelte verhindern
            hash_id = f"{titel}-{beginn}"
            if hash_id in gefundene_hashes: continue
            gefundene_hashes.add(hash_id)
            gefunden = True
            
            print(f"Gefunden: {titel} -> {beginn}")

            # --- TEIL C: SENDEN (Ohne Emoji im Title Header!) ---
            # Das Emoji 🚗 kommt in den Body oder Tags, NICHT in den Title-Header (das hat den Crash verursacht)
            
            nachricht_body = f"Einlass: {einlass} Uhr\nBeginn: {beginn} Uhr"
            
            requests.post(
                f"https://ntfy.sh/{KANAL_NAME}",
                data=nachricht_body.encode('utf-8'),
                headers={
                    "Title": titel,       # Nur Text, kein Emoji hier!
                    "Priority": "high",
                    "Tags": "car,ticket", # Hier sind die Emojis sicher
                    "Click": url          # Link zum Anklicken
                }
            )

        if not gefunden:
            print("Nichts gefunden.")

    except Exception as e:
        print(f"Fehler: {e}")
        # Fehler melden
        requests.post(f"https://ntfy.sh/{KANAL_NAME}", data=f"Fehler: {e}", headers={"Title": "Skript Error"})

if __name__ == "__main__":
    check_events()
