import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import sys

# --- DEIN KANAL ---
KANAL_NAME = "max-schmeling-halle-warner"
# ------------------

def send_to_handy(titel, text, tags="warning"):
    """Hilfsfunktion: Sendet garantiert eine Nachricht"""
    try:
        requests.post(
            f"https://ntfy.sh/{KANAL_NAME}",
            data=text.encode('utf-8'),
            headers={
                "Title": titel,
                "Priority": "high",
                "Tags": tags
            }
        )
    except:
        pass

def check_events():
    print("Starte Check...")
    try:
        url = "https://www.max-schmeling-halle.de/events-tickets"
        
        # 1. Webseite laden
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        response.raise_for_status() # Bricht ab, wenn Webseite down ist
        
        # Text holen
        soup = BeautifulSoup(response.text, 'html.parser')
        full_text = soup.get_text(" | ", strip=True)

        # 2. Datum suchen
        heute = datetime.now()
        monate = {1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
                  7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"}
        
        datum_kurz = heute.strftime("%d.%m.%Y")       # 16.02.2026
        datum_text = f"{int(heute.strftime('%d'))}. {monate[heute.month]}" # 16. Februar
        
        gefunden = False
        
        # Wir suchen nach BEIDEN Datums-Varianten
        suchbegriffe = [datum_kurz, datum_text]
        
        for datum in suchbegriffe:
            if datum in full_text:
                # Datum gefunden! Jetzt suchen wir die Details in der Nähe.
                found_idx = full_text.find(datum)
                
                # Wir schneiden uns ein Stück Text aus (300 Zeichen davor und danach)
                start = max(0, found_idx - 300)
                end = min(len(full_text), found_idx + 400)
                ausschnitt = full_text[start:end]
                
                # UHRZEITEN FINDEN
                einlass = "??"
                beginn = "??"
                
                # Suche nach Uhrzeiten (Muster: 18:00 oder 19.30)
                e_match = re.search(r"Einlass.*?(\d{1,2}[:.]\d{2})", ausschnitt, re.IGNORECASE)
                if e_match: einlass = e_match.group(1).replace('.', ':')
                
                b_match = re.search(r"Beginn.*?(\d{1,2}[:.]\d{2})", ausschnitt, re.IGNORECASE)
                if b_match: beginn = b_match.group(1).replace('.', ':')

                # TITEL FINDEN (Der Text VOR dem Datum)
                teile = ausschnitt.split(datum)
                text_davor = teile[0]
                # Wir nehmen die letzten Worte vor dem Datum als Titel
                worte = text_davor.split("|")
                titel = "Event heute"
                if len(worte) >= 2:
                    # Nimm das vorletzte Element, das ist meist der Titel
                    kandidat = worte[-1].strip()
                    if len(kandidat) < 3: kandidat = worte[-2].strip()
                    titel = kandidat
                
                if len(titel) > 40: titel = titel[:37] + "..."

                # Nachricht senden!
                msg = f"Einlass: {einlass} Uhr\nBeginn: {beginn} Uhr"
                send_to_handy(f"Heute: {titel}", msg, "ticket")
                gefunden = True
                break # Nur das erste Event melden (verhindert Spam)

        if not gefunden:
            print("Kein Event gefunden.")
            # Optional: Sende Nachricht, dass Skript lief (zum Testen)
            # send_to_handy("Status OK", "Kein Event heute gefunden.", "white_check_mark")

    except Exception as e:
        # HIER IST DER RETTER: Wenn was schief geht, sendet er den Fehler ans Handy!
        error_msg = str(e)
        print(f"CRASH: {error_msg}")
        send_to_handy("Skript Fehler ⚠️", f"Hilfe, ich bin abgestürzt:\n{error_msg}", "rotating_light")
        sys.exit(1) # Markiert den Run bei GitHub als rot

if __name__ == "__main__":
    check_events()
