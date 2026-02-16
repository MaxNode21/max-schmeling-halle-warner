import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

# --- DEIN KANAL ---
KANAL_NAME = "max-schmeling-halle-warner"
# ------------------

def get_german_date():
    # Wir bauen das Datum so, wie es auf der Webseite steht (z.B. "16. Februar 2026")
    heute = datetime.now()
    monate = {
        1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
        7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
    }
    # Formate, nach denen wir suchen: "16.02.2026" und "16. Februar 2026"
    return [
        heute.strftime("%d.%m.%Y"),
        f"{int(heute.strftime('%d'))}. {monate[heute.month]} {heute.year}"
    ]

def check_events():
    url = "https://www.max-schmeling-halle.de/events-tickets"
    print(f"Prüfe {url}...")
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text(" ", strip=True) # Text sauber machen

        date_strings = get_german_date()
        gefunden = False
        details = ""

        # Wir suchen nach dem Datum im Text
        for datum in date_strings:
            if datum in text:
                gefunden = True
                print(f"Datum gefunden: {datum}")
                
                # Wir versuchen, den Text-Schnipsel um das Datum herum zu finden, 
                # um Startzeiten zu extrahieren.
                # (Einfache Suche im Umkreis von 100 Zeichen nach dem Datum)
                index = text.find(datum)
                umfeld = text[index:index+300] # Die nächsten 300 Zeichen lesen
                
                # Suche nach Uhrzeiten (Muster: "19:30" oder "19:30 Uhr")
                # Wir suchen spezifisch nach "Beginn" und "Einlass"
                beginn_match = re.search(r"Beginn[:\s]*(\d{1,2}:\d{2})", umfeld, re.IGNORECASE)
                einlass_match = re.search(r"Einlass[:\s]*(\d{1,2}:\d{2})", umfeld, re.IGNORECASE)
                
                start_zeit = beginn_match.group(1) if beginn_match else "??"
                einlass_zeit = einlass_match.group(1) if einlass_match else "??"
                
                details = f"Beginn: {start_zeit} Uhr | Einlass: {einlass_zeit} Uhr"
                break # Wenn gefunden, hören wir auf zu suchen

        if gefunden:
            nachricht = f"Heute Event! 🎤\n{details}\n(Ende unbekannt)"
            print(f"Sende: {nachricht}")
            
            requests.post(
                f"https://ntfy.sh/{KANAL_NAME}",
                data=nachricht.encode('utf-8'),
                headers={
                    "Title": "Event heute in der Halle!",
                    "Priority": "high",
                    "Tags": "tada,clock"
                }
            )
        else:
            print("Heute kein Event gefunden.")

    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    check_events()
