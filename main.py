import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import math

# --- KONFIGURATION ---
KANAL_NAME = "max-schmeling-halle-warner"
TEST_MODUS = True  # <--- WICHTIG: Zum Testen auf True lassen. 
                   # Wenn der Text auf dem Handy PERFEKT ist, auf False stellen!
# ---------------------

def check_events():
    url = "https://www.max-schmeling-halle.de/events-tickets"
    print(f"--- Prüfe {url} ---")

    # Datum vorbereiten
    heute = datetime.now()
    monate = {1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
              7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"}
    
    # Wir suchen nach "16.02.2026" und "16. Februar"
    datum_kurz = heute.strftime("%d.%m.%Y")
    datum_lang = f"{int(heute.strftime('%d'))}. {monate[heute.month]}"
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # TRICK: Wir nutzen ein Trennzeichen "|", damit Titel und Datum nicht zusammenkleben
        text_full = soup.get_text(" | ", strip=True)

        gefunden = False
        gefundene_hashes = set()

        # Wir suchen nach dem Datum im ganzen Text
        # finditer findet alle Events des Tages
        for match in re.finditer(re.escape(datum_kurz), text_full):
            found_index = match.start()
            
            # Wir schauen uns den Text Umkreis an (200 Zeichen davor, 400 danach)
            umfeld_start = max(0, found_index - 200)
            umfeld_ende = min(len(text_full), found_index + 400)
            umfeld = text_full[umfeld_start:umfeld_ende]

            # 1. ZEITEN FINDEN (Robust!)
            einlass = "??"
            beginn = "??"
            
            e_match = re.search(r"Einlass.*?(\d{1,2}:\d{2})", umfeld, re.IGNORECASE)
            if e_match: einlass = e_match.group(1)
            
            b_match = re.search(r"Beginn.*?(\d{1,2}:\d{2})", umfeld, re.IGNORECASE)
            if b_match: beginn = b_match.group(1)

            # 2. TITEL RATEN (Wir nehmen den Textteil VOR dem Datum)
            # Das Datum steht im 'umfeld' etwa bei Index 200. Wir schauen davor.
            # Wir suchen nach dem Stück Text zwischen dem letzten "|" und dem Datum.
            teil_vor_datum = umfeld[:200].split("|")
            
            # Der Titel ist meistens das letzte oder vorletzte Element vor dem Datum
            titel = "Event"
            if len(teil_vor_datum) >= 2:
                moglicher_titel = teil_vor_datum[-1].strip()
                # Wenn das nur Müll ist (zu kurz), nehmen wir das davor
                if len(moglicher_titel) < 3:
                    moglicher_titel = teil_vor_datum[-2].strip()
                
                # Datum aus Titel entfernen, falls es noch drin hängt
                titel = moglicher_titel.replace(datum_kurz, "").replace(datum_lang, "").strip()
            
            if len(titel) > 40: titel = titel[:37] + "..." # Kürzen wenn zu lang

            # Doppelte verhindern
            event_hash = f"{titel}-{beginn}"
            if event_hash in gefundene_hashes: continue
            gefundene_hashes.add(event_hash)
            gefunden = True

            print(f"Gefunden: {titel} | Einlass: {einlass} | Beginn: {beginn}")

            # 3. VERZÖGERUNG BERECHNEN (Ohne pytz, einfache Mathematik)
            delay_text = ""
            tag = "ticket" # Standard Icon
            
            if TEST_MODUS:
                print(" -> TEST: Sende sofort")
            elif einlass != "??":
                # Wir rechnen: Einlass (z.B. 18:00) minus Jetzt (z.B. 08:00) minus 2 Std Puffer
                h_einlass, m_einlass = map(int, einlass.split(':'))
                
                # Aktuelle Stunde in Deutschland (Server ist UTC, DE ist UTC+1 im Winter)
                # Wir machen es einfach: Wir nutzen die Serverzeit und rechnen +1 Stunde drauf
                jetzt_utc = datetime.utcnow()
                jetzt_de_stunde = jetzt_utc.hour + 1 
                
                # Minuten bis zum Einlass
                minuten_bis_einlass = (h_einlass * 60 + m_einlass) - (jetzt_de_stunde * 60 + jetzt_utc.minute)
                
                # Wir wollen 2 Stunden (120 Min) VORHER warnen
                minuten_delay = minuten_bis_einlass - 120
                
                if minuten_delay > 0:
                    delay_text = f"{minuten_delay}m"
                    tag = "clock" # Uhr Icon für geplante Nachricht
                    print(f" -> Verzögerung: {minuten_delay} Minuten")
                else:
                    print(" -> Zu spät für Verzögerung, sende sofort.")

            # 4. NACHRICHT SENDEN (Kurz & Knapp)
            # Nachricht: "Titel (Start: 19:30)"
            # Body: "Einlass: 18:00"
            
            requests.post(
                f"https://ntfy.sh/{KANAL_NAME}",
                data=f"Einlass: {einlass} Uhr\nBeginn: {beginn} Uhr".encode('utf-8'),
                headers={
                    "Title": f"{titel}", # Nur der Titel oben
                    "Priority": "high",
                    "Tags": tag,
                    "Delay": delay_text
                }
            )

    except Exception as e:
        print(f"Fehler: {e}")
        # Nur im Testmodus Fehler senden
        if TEST_MODUS:
             requests.post(f"https://ntfy.sh/{KANAL_NAME}", data=f"Fehler: {e}", headers={"Title": "Skript Fehler"})

if __name__ == "__main__":
    check_events()
