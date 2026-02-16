import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

# --- KONFIGURATION ---
KANAL_NAME = "max-schmeling-halle-warner"
TEST_MODUS = True   # <--- WICHTIG: Erst True lassen zum Testen!
# ---------------------

def check_events():
    url = "https://www.max-schmeling-halle.de/events-tickets"
    print(f"--- Prüfe {url} ---")
    
    # 1. Datum bestimmen
    heute = datetime.now()
    monate = {1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
              7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"}
    
    # Such-Strings: "16.02.2026" und "16. Februar"
    datum_kurz = heute.strftime("%d.%m.%Y")
    datum_lang = f"{int(heute.strftime('%d'))}. {monate[heute.month]}"
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        # WICHTIG: Wir holen den rohen Text mit Trennzeichen, damit nichts zusammenklebt
        soup = BeautifulSoup(response.text, 'html.parser')
        full_text = soup.get_text(" | ", strip=True)

        gefunden = False
        gefundene_hashes = set()
        
        # Wir suchen nach dem Datum im gesamten Text (das hat um 22:10 Uhr funktioniert!)
        # Wir nehmen das Datum, das zuerst gefunden wird.
        for match in re.finditer(re.escape(datum_kurz), full_text):
            found_idx = match.start()
            
            # 2. Text-Ausschnitt holen (Großzügig: 300 Zeichen davor, 500 danach)
            # Damit erwischen wir Titel (davor) und Uhrzeiten (danach) sicher.
            start_pos = max(0, found_idx - 300)
            end_pos = min(len(full_text), found_idx + 500)
            ausschnitt = full_text[start_pos:end_pos]
            
            # Debug-Ausgabe im Log sehen
            # print(f"Prüfe Ausschnitt: {ausschnitt[:50]}...")

            # 3. UHRZEITEN FINDEN (Robuste Regex-Suche im Ausschnitt)
            einlass = "??"
            beginn = "??"
            
            # Suche nach Uhrzeit-Mustern (HH:MM)
            e_match = re.search(r"Einlass.*?(\d{1,2}:\d{2})", ausschnitt, re.IGNORECASE)
            if e_match: einlass = e_match.group(1)
            
            b_match = re.search(r"Beginn.*?(\d{1,2}:\d{2})", ausschnitt, re.IGNORECASE)
            if b_match: beginn = b_match.group(1)

            # 4. TITEL FINDEN (Alles VOR dem Datum im Ausschnitt)
            # Wir splitten den Ausschnitt am Datum. Der Teil davor ist der Titel.
            parts = ausschnitt.split(datum_kurz)
            if len(parts) > 0:
                text_davor = parts[0]
                # Wir nehmen das letzte Stück Text vor dem Datum (getrennt durch |)
                titel_teile = text_davor.split("|")
                # Nimm das letzte Element, das lang genug ist (um "Montag" etc. zu überspringen)
                titel = "Event"
                for teil in reversed(titel_teile):
                    teil = teil.strip()
                    # Ignoriere Wochentage oder leeren Kram
                    if len(teil) > 3 and "Montag" not in teil and "Dienstag" not in teil:
                        titel = teil
                        break
                
                # Titel säubern
                if len(titel) > 50: titel = titel[:47] + "..."
            else:
                titel = "Event"

            # Check: Haben wir das Event schon?
            hash_id = f"{titel}-{beginn}"
            if hash_id in gefundene_hashes: continue
            gefundene_hashes.add(hash_id)
            gefunden = True
            
            print(f"Treffer: {titel} | Einlass: {einlass} | Beginn: {beginn}")

            # 5. VERZÖGERUNG BERECHNEN
            delay_str = ""
            tag = "ticket"
            
            if TEST_MODUS:
                print("Test-Modus aktiv: Sende sofort.")
            elif einlass != "??":
                # Einfache Rechnung (UTC+1 Winterzeit Annahme)
                try:
                    utc_now = datetime.utcnow()
                    de_hour = utc_now.hour + 1 # Winterzeit
                    
                    h_einlass = int(einlass.split(':')[0])
                    m_einlass = int(einlass.split(':')[1])
                    
                    min_now = de_hour * 60 + utc_now.minute
                    min_einlass = h_einlass * 60 + m_einlass
                    
                    # 120 Minuten vorher warnen
                    wait_min = min_einlass
