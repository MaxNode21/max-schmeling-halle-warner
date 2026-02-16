import requests
from bs4 import BeautifulSoup
from datetime import datetime

# --- HIER DEINEN KANALNAMEN EINTRAGEN ---
KANAL_NAME = "max-schmeling-halle-warner"  # <--- Ändere das zu dem Namen aus Schritt 1 !!
# ----------------------------------------

def check_events():
    url = "https://www.max-schmeling-halle.de/events-tickets"
    print(f"Prüfe {url}...")
    
    try:
        # Webseite laden
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        
        # Heutiges Datum holen (z.B. "16.02.2024" und "16.02.24")
        heute = datetime.now()
        datum_lang = heute.strftime("%d.%m.%Y") 
        datum_kurz = heute.strftime("%d.%m.%y")
        
        # Prüfen ob Datum im Text der Webseite steht
        if datum_lang in response.text or datum_kurz in response.text:
            nachricht = f"Achtung! Heute ({datum_lang}) ist ein Event in der Max-Schmeling-Halle!"
            print("Event gefunden! Sende Nachricht...")
            
            # Nachricht an Handy senden
            requests.post(
                f"https://ntfy.sh/{KANAL_NAME}",
                data=nachricht.encode('utf-8'),
                headers={"Title": "Parkplatz Alarm 🚗", "Priority": "high"}
            )
        else:
            print(f"Kein Event für heute ({datum_lang}) gefunden.")

    except Exception as e:
        print(f"Fehler passiert: {e}")

if __name__ == "__main__":
    check_events()
