import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

# --- KONFIGURATION ---
KANAL_NAME = "max-schmeling-halle-warner"
TEST_MODUS = True   # <--- Lass das auf True, bis die erste Nachricht sauber ankam!
# ---------------------

def check_events():
    url = "https://www.max-schmeling-halle.de/events-tickets"
    print(f"--- Prüfe {url} ---")
    
    # Datum bestimmen
    heute = datetime.now()
    monate = {1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
              7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"}
    
    datum_kurz = heute.strftime("%d.%m.%Y")       # z.B. 16.02.2026
    datum_text = f"{int(heute.strftime('%d'))}. {monate[heute.month]}" # z.B. 16. Februar
    jahr = str(heute.year)

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        gefunden = False
        gefundene_hashes = set()

        # Wir suchen direkt nach dem Text "16. Februar" (oder aktuelles Datum)
        # und hangeln uns von dort zum Event-Container.
        suchbegriffe = [datum_text, datum_kurz]
        
        for suchwort in suchbegriffe:
            for element in soup.find_all(string=re.compile(re.escape(suchwort))):
                
                # Gehe 3 Ebenen hoch, um den ganzen Kasten zu finden
                container = element.parent.parent.parent
                if not container: continue
                
                # WICHTIG: separator=" " verhindert "TitelDatum"-Salat!
                text_sauber = container.get_text(" ", strip=True)
                
                # Prüfen, ob das Datum wirklich drin ist (zur Sicherheit)
                if suchwort not in text_sauber:
                    continue

                # 1. ZEITEN FINDEN
                einlass = "??"
                beginn = "??"
                
                e_match = re.search(r"Einlass.*?(\d{1,2}:\d{2})", text_sauber, re.IGNORECASE)
                if e_match: einlass = e_match.group(1)
                
                b_match = re.search(r"Beginn.*?(\d{1,2}:\d{2})", text_sauber, re.IGNORECASE)
                if b_match: beginn = b_match.group(1)

                # 2. TITEL ISOLIEREN
                # Wir nehmen den Text und schneiden alles ab dem Datum ab.
                # Meistens steht der Titel VOR dem Datum.
                parts = text_sauber.split(suchwort)
                titel_roh = parts[0] # Alles vor dem Datum
                
                # Den Titel noch etwas säubern (Wochentage etc. entfernen)
                titel = titel_roh.replace("Montag,", "").replace("Dienstag,", "").replace("Mittwoch,", "").replace("Donnerstag,", "").replace("Freitag,", "").replace("Samstag,", "").replace("Sonntag,", "").strip()
                
                # Falls Titel leer oder zu kurz, Fallback
                if len(titel) < 5:
                    titel = "Event in der Halle"

                if len(titel) > 50: titel = titel[:47] + "..."

                # Doppelte verhindern
                hash_id = f"{titel}-{beginn}"
                if hash_id in gefundene_hashes: continue
                gefundene_hashes.add(hash_id)
                gefunden = True
                
                print(f"Gefunden: {titel} | {beginn}")

                # 3. VERZÖGERUNG BERECHNEN (Simpel)
                delay_str = ""
                tag = "ticket"
                
                if TEST_MODUS:
                    print("Test-Modus: Sende sofort.")
                elif einlass != "??":
                    # Einfache Rechnung: Einlass-Stunde + 1 (für Winterzeit DE) - 2 Std Puffer
                    # Wir nutzen UTC vom Server.
                    utc_now = datetime.utcnow()
                    de_hour = utc_now.hour + 1 # Winterzeit! (+2 im Sommer)
                    
                    h_einlass = int(einlass.split(':')[0])
                    m_einlass = int(einlass.split(':')[1])
                    
                    # Minuten seit Tagesbeginn
                    min_now = de_hour * 60 + utc_now.minute
                    min_einlass = h_einlass * 60 + m_einlass
                    
                    # Alarm in Minuten (Einlass - Jetzt - 120 Min Puffer)
                    wait_min = min_einlass - min_now - 120
                    
                    if wait_min > 0:
                        delay_str = f"{wait_min}m"
                        tag = "clock"
                        print(f"Verzögerung: {wait_min} Minuten")

                # 4. SENDEN
                requests.post(
                    f"https://ntfy.sh/{KANAL_NAME}",
                    data=f"Einlass: {einlass} Uhr\nBeginn: {beginn} Uhr".encode('utf-8'),
                    headers={
                        "Title": titel,
                        "Priority": "high",
                        "Tags": tag,
                        "Delay": delay_str
                    }
                )

        if not gefunden:
            print("Nichts gefunden.")
            # Damit du weißt, dass das Skript überhaupt lief:
            if TEST_MODUS:
                requests.post(f"https://ntfy.sh/{KANAL_NAME}", 
                              data="Skript lief erfolgreich durch, aber heute ist kein Event.".encode('utf-8'),
                              headers={"Title": "Check OK (Kein Event)"})

    except Exception as e:
        print(f"Fehler: {e}")
        if TEST_MODUS:
            requests.post(f"https://ntfy.sh/{KANAL_NAME}", data=f"Fehler: {e}", headers={"Title": "Skript Error"})

if __name__ == "__main__":
    check_events()
