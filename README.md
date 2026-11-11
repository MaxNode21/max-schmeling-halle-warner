# Max-Schmeling-Halle-Warner

Schaut jeden Morgen auf die [Eventseite der Max-Schmeling-Halle](https://www.max-schmeling-halle.de/events)
und schickt eine Push-Nachricht aufs Handy, wenn dort heute eine Veranstaltung ist.

Läuft komplett über GitHub Actions, die Nachrichten kommen über [ntfy](https://ntfy.sh).

## Einrichten

1. ntfy-App installieren und einen **schwer zu erratenden** Kanal abonnieren, z. B. mit diesem Namen:
   `python -c "import secrets; print('msh-' + secrets.token_urlsafe(12))"`
   ntfy-Kanäle sind öffentlich: Wer den Namen kennt, kann mitlesen und dir Nachrichten schicken.
   Deshalb steht der Name nicht im Code.
2. Im Repo unter **Settings → Secrets and variables → Actions** ein Secret `NTFY_TOPIC` mit dem Namen anlegen.
3. Unter **Actions → Parkplatz Checker → Run workflow** den Modus `testnachricht` starten und prüfen, ob die Nachricht ankommt.

## Manuell starten

**Run workflow** hat drei Modi:

| Modus | Was passiert |
|---|---|
| `normal` | wie der tägliche Lauf |
| `testnachricht` | schickt nur eine Test-Nachricht |
| `trockenlauf` | sendet nichts, zeigt im Log alle erkannten Termine und die Nachrichten, die rausgehen würden |

Optional lässt sich ein anderes Datum (JJJJ-MM-TT) prüfen, z. B. ein Tag, an dem sicher etwas los ist.

Lokal:

```sh
pip install -r requirements.txt
python main.py --dry-run
python main.py --dry-run --datum 2026-11-14
python -m unittest -v
```

## Gut zu wissen

- Der Check läuft täglich um 07:47 Uhr Berliner Zeit. GitHub startet geplante Läufe manchmal etwas später.
- GitHub schaltet geplante Workflows in öffentlichen Repos ab, wenn 60 Tage lang nichts im Repo passiert ist.
  Dann unter **Actions → Parkplatz Checker** auf **Enable workflow** klicken.
- Erkennt das Skript gar keine Termine mehr (z. B. nach einem Website-Umbau), kommt eine Fehler-Push mit Link zum Log.
