import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import re
import time

# --- KONFIGURATION ---
KANAL_NAME = "max-schmeling-halle-warner"
TEST_MODUS = True  # <--- HIER: Auf True setzen zum Testen (sofortige Nachricht)
                   # <--- HIER: Auf False setzen für den echten Betrieb (2 Std vorher)
# ---------------------

def get_german_date():
    """Erzeugt Datum-Strings für die Suche"""
    heute = datetime.now()
    monate = {
        1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
        7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
    }
    return [
        heute.strftime("%d.%m.%Y"),         # 16.02.2026
        f"{int(heute.strftime('%d'))}. {monate[heute.month]} {heute.year}" # 16. Februar 2026
    ]

def check_events():
    url = "https://www.max-schmeling-halle.de/events-tickets"
    print(f"--- Prüfe {url} ---")
    print(f"Modus: {'TEST (Sofort)' if TEST_MODUS else 'LIVE (Verzögert)'}")

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text(" ", strip=True) # Robuste Textsuche

        date_strings = get_german_date()
        gefunden_hashes = set()
        
        found_any = False

        for datum in date_strings:
            # Suche alle Vorkommen des Datums
            for match in re.finditer(re.escape(datum), text):
                
                # Umfeld analysieren (300 Zeichen danach)
                start = match.start()
                umfeld = text[start:start+400]
                
                # Uhrzeiten extrahieren
                beginn_match = re.search(r"Beginn[:\s]*(\d{1,2}:\d{2})", umfeld, re.IGNORECASE)
                einlass_match = re.search(r"Einlass[:\s]*(\d{1,2}:\d{2})", umfeld, re.IGNORECASE)
                
                start_zeit = beginn_match.group(1) if beginn_match else "??"
                einlass_zeit = einlass_match.group(1) if einlass_match else "??"
                
                # Titel raten: Wir nehmen einfach die 50 Zeichen VOR dem Datum als Titel-Hinweis
                # oder kurz nach dem Datum, falls davor nichts Sinnvolles steht.
                # Simpler Fallback für die Nachricht:
                titel_info = "Event" 

                # Hash um Doppelte zu vermeiden (nur Zeitbasiert)
                event_hash = f"{start_zeit}-{einlass_zeit}"
                if event_hash in gefunden_hashes:
                    continue
                gefunden_hashes.add(event_hash)
                found_any = True

                print(f"Gefunden! Beginn: {start_zeit}, Einlass: {einlass_zeit}")

                # --- VERZÖGERUNG BERECHNEN ---
                delay_header = ""
                
                if TEST_MODUS:
                    print("  -> Test-Modus: Sende sofort!")
                    msg_prefix = "[TEST] "
                else:
                    msg_prefix = ""
                    # Wenn wir eine Einlasszeit haben, rechnen wir!
                    if einlass_zeit != "??":
                        # Wir nehmen an, die Webseite zeigt deutsche Zeit.
                        # Wir müssen das in einen Unix-Timestamp wandeln.
                        
                        uhr_h, uhr_m = map(int, einlass_zeit.split(':'))
                        jetzt = datetime.now()
                        
                        # Event-Zeitpunkt erstellen (Naive)
                        event_dt = jetzt.replace(hour=uhr_h, minute=uhr_m, second=0, microsecond=0)
                        
                        # Alarm = 2 Stunden vorher
                        alarm_dt = event_dt - timedelta(hours=2)
                        
                        # Zeitzonen-Korrektur: 
                        # GitHub läuft auf UTC. Deutschland ist UTC+1 (Winter) oder UTC+2 (Sommer).
                        # Das Skript liest "18:00" -> interpretiert als 18:00 UTC (falsch).
                        # Wir müssen also 1 Stunde abziehen, damit der Timestamp stimmt?
                        # Einfacher Trick: Wir berechnen die Differenz in Sekunden und nutzen "Delay: Xs"
                        
                        # Da "jetzt" auf dem Server UTC ist und "event_dt" deutsche Zeit sein soll:
                        # Wir tun so, als wäre "event_dt" auch UTC, müssen aber den Zeitunterschied (1h) draufrechnen.
                        # Noch einfacher: ntfy nimmt "Delay: 2h". Wir rechnen die Stunden aus.
                        
                        # Aktuelle Serverzeit (UTC)
                        now_utc = datetime.now(timezone.utc)
                        # Event Zeit in Deutschland (grob UTC+1 annehmen für Winter)
                        # Wir bauen uns ein offset-aware datetime für Berlin
                        berlin_offset = timezone(timedelta(hours=1)) # Winterzeit! (Im Sommer hours=2)
                        event_berlin = datetime.now(berlin_offset).replace(hour=uhr_h, minute=uhr_m, second=0, microsecond=0)
                        
                        # Wann soll der Alarm sein?
                        alarm_zeit = event_berlin - timedelta(hours=2)
                        
                        # Wie viele Sekunden sind es von JETZT bis ALARM?
                        seconds_left = (alarm_zeit - now_utc).total_seconds()
                        
                        if seconds_left > 0:
                            print(f"  -> Alarm in {int(seconds_left/60)} Minuten geplant ({alarm_zeit})")
                            delay_header = f"{int(seconds_left)}s"
                        else:
                            print("  -> Alarm-Zeit schon vorbei, sende sofort.")

                # Nachricht bauen
                nachricht = f"{msg_prefix}Bald geht's los! 🎤\nEinlass: {einlass_zeit} Uhr\nBeginn: {start_zeit} Uhr"
                
                requests.post(
                    f"https://ntfy.sh/{KANAL_NAME}",
                    data=nachricht.encode('utf-8'),
                    headers={
                        "Title": f"Event heute: {start_zeit} Uhr",
                        "Priority": "high",
                        "Tags": "ticket,music",
                        "Delay": delay_header
                    }
                )

        if not found_any:
            print(f"Keine Events für heute ({date_strings[0]}) gefunden.")
            # Optional für Test:
            if TEST_MODUS:
                print("Test-Modus aktiv: Sende trotzdem eine 'Kein Event' Nachricht zum Prüfen.")
                requests.post(f"https://ntfy.sh/{KANAL_NAME}", data="Test erfolgreich: Skript läuft, aber heute ist kein Event.".encode('utf-8'), headers={"Title": "Test OK"})

    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    check_events()
