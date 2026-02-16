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
    
    # Datum von heute
    heute = datetime.now()
    monate = {1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
              7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"}
    
    datum_kurz = heute.strftime("%d.%m.%Y")       # 16.02.2026
    datum_lang = f"{int(heute.strftime('%d'))}. {monate[heute.month]}" # 16. Februar
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text(" ", strip=True)

        gefunden = False
        
        # Wir suchen simpel nach dem Datum
        suchbegriffe = [datum_kurz, datum_lang]
        
        for datum in suchbegriffe:
            if datum in text:
                # Datum gefunden -> Es ist ein Event!
                
                # Wir suchen im Umkreis nach Uhrzeiten
                index = text.find(datum)
                umfeld = text[index:index+400]
                
                einlass = "??"
                beginn = "??"
                
                e_match = re.search(r"Einlass.*?(\d{1,2}[:.]\d{2})", umfeld, re.IGNORECASE)
                if e_match: einlass = e_match.group(1).replace('.', ':')
                
                b_match = re.search(r"Beginn.*?(\d{1,2}[:.]\d{2})", umfeld, re.IGNORECASE)
                if b_match: beginn = b_match.group(1).replace('.', ':')

                # NACHRICHT SENDEN
                # Statt dem Titel senden wir einfach den Link!
                nachricht = f"Einlass: {einlass} Uhr\nBeginn: {beginn} Uhr\n\n👉 Wer spielt? Hier klicken:\n{url}"
                
                requests.post(
                    f"https://ntfy.sh/{KANAL_NAME}",
                    data=nachricht.encode('utf-8'),
                    headers={
                        "Title": "🚗 Parkplatz-Alarm!", # Immer gleicher Titel
                        "Priority": "high",
                        "Tags": "car,traffic_light",
                        "Click": url # Wenn er auf die Nachricht tippt, öffnet sich die Webseite
                    }
                )
                
                gefunden = True
                print("Event gemeldet.")
                break # Einmal melden reicht

        if not gefunden:
            print("Heute kein Event.")

    except Exception as e:
        print(f"Fehler: {e}")
        # Fehler melden, damit man weiß, was los ist
        requests.post(f"https://ntfy.sh/{KANAL_NAME}", data=f"Fehler: {e}", headers={"Title": "Skript Fehler"})

if __name__ == "__main__":
    check_events()
