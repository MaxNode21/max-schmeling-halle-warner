"""Tests ohne Netzwerk: python -m unittest -v"""

import io
import os
import unittest
from contextlib import redirect_stdout
from datetime import date
from unittest import mock

import main

# Nachgebaut nach dem Aufbau der Eventseite: Jede Veranstaltung ist ein Link
# mit Datum, Uhrzeit, Titel, Status und Button-Text.
BEISPIELSEITE = """<!doctype html>
<html lang="de"><head><meta charset="utf-8"><title>Events</title></head>
<body>
<nav><a href="/events">Events</a> <a href="/kontakt">Kontakt</a></nav>

<a href="/events/event/fuechse-berlin-vs-thw-kiel-max-schmeling-halle-2026-11-14">
  <span>Sa., 14. Nov '26</span> <span>15:55 Uhr</span>
  <h3>Füchse Berlin vs. THW Kiel</h3> <p>Handball-Bundesliga 2026/27</p>
  <span>Im Vorverkauf erhältlich</span> <span>Tickets</span>
</a>
<a href="/events/event/fuechse-berlin-vs-thw-kiel-max-schmeling-halle-2026-11-14">
  <span>Sa., 14. Nov '26</span> <span>15:55 Uhr</span>
  <h3>Füchse Berlin vs. THW Kiel</h3> <p>Handball-Bundesliga 2026/27</p>
  <span>Im Vorverkauf erhältlich</span> <span>Tickets</span>
</a>

<a href="/events/event/rin-max-schmeling-halle-2026-11-27">
  <span>Fr., 27. Nov '26</span> <span>20:00 Uhr</span>
  <h3>RIN</h3> <p>Nostalgia Tour</p> <span>verschoben</span> <span>Infos</span>
</a>
<a href="/events/event/rin-ohne-uhrzeit">
  <span>Fr., 27. Nov '26</span> <h3>RIN ohne Uhrzeit</h3>
</a>

<a href="/events/event/berq-max-schmeling-halle-2026-11-28">
  <span>Samstag, 28. November 2026</span> <span>20:00 Uhr</span>
  <h3>berq</h3> <p>Tour 2026</p> <span>ausverkauft</span> <span>Infos</span>
</a>

<a href="https://tickets.example/tattoo-abend"><span>Sa., 7. Nov ’26</span>
  <span>19:00 Uhr</span><h3>Berlin Tattoo</h3></a>
<a href="https://tickets.example/tattoo-mittag"><span>Sa., 7. Nov ’26</span>
  <span>13:30 Uhr</span><h3>Berlin Tattoo</h3></a>

<a href="/events/event/kaputt"><span>Mo., 31. Feb '27</span>
  <span>19:00 Uhr</span><h3>Kaputtes Datum</h3></a>

<a href="/events/event/messe"><span>Mi., 3. Mär. '27</span>
  <span>9.30 Uhr</span><h3>Frühjahrsmesse</h3></a>
</body></html>
"""


def events():
    with redirect_stdout(io.StringIO()):
        return main.extract_events(BEISPIELSEITE)


def finde(titel):
    return next(event for event in events() if event.title == titel)


class ExtractEventsTest(unittest.TestCase):
    def test_erkennt_termin_mit_allen_feldern(self):
        event = finde("Füchse Berlin vs. THW Kiel Handball-Bundesliga 2026/27")
        self.assertEqual(event.day, date(2026, 11, 14))
        self.assertEqual(event.start, "15:55")
        self.assertEqual(
            event.url,
            "https://www.max-schmeling-halle.de/events/event/"
            "fuechse-berlin-vs-thw-kiel-max-schmeling-halle-2026-11-14",
        )
        self.assertIsNone(event.status)

    def test_ignoriert_doppelte_links_navigation_und_termine_ohne_uhrzeit(self):
        titel = [event.title for event in events()]
        self.assertEqual(
            sorted(titel),
            sorted(
                [
                    "Füchse Berlin vs. THW Kiel Handball-Bundesliga 2026/27",
                    "RIN Nostalgia Tour",
                    "berq Tour 2026",
                    "Berlin Tattoo",
                    "Berlin Tattoo",
                    "Frühjahrsmesse",
                ]
            ),
        )

    def test_ungueltiges_datum_wird_uebersprungen_statt_abzustuerzen(self):
        with redirect_stdout(io.StringIO()) as ausgabe:
            gefunden = main.extract_events(BEISPIELSEITE)
        self.assertNotIn("Kaputtes Datum", [event.title for event in gefunden])
        self.assertIn("ungültigem Datum", ausgabe.getvalue())

    def test_statushinweis_wird_erkannt_und_aus_titel_entfernt(self):
        self.assertEqual(finde("RIN Nostalgia Tour").status, "verschoben")
        self.assertIsNone(finde("berq Tour 2026").status)

    def test_demnaechst_im_vorverkauf_wird_entfernt(self):
        self.assertEqual(
            main.clean_event_title(
                " Pro Climbing League Finals demnächst im Vorverkauf"
            ),
            "Pro Climbing League Finals",
        )

    def test_ausgeschriebene_namen_und_vierstelliges_jahr(self):
        self.assertEqual(finde("berq Tour 2026").day, date(2026, 11, 28))

    def test_monat_mit_punkt_und_uhrzeit_mit_punkt(self):
        messe = finde("Frühjahrsmesse")
        self.assertEqual(messe.day, date(2027, 3, 3))
        self.assertEqual(messe.start, "09:30")

    def test_bytes_mit_umlauten_werden_richtig_dekodiert(self):
        with redirect_stdout(io.StringIO()):
            gefunden = main.extract_events(BEISPIELSEITE.encode("utf-8"))
        self.assertEqual(
            sorted(e.title for e in gefunden), sorted(e.title for e in events())
        )
        self.assertIn(date(2027, 3, 3), [event.day for event in gefunden])


class CategorizeTest(unittest.TestCase):
    def test_sport(self):
        for titel in (
            "Füchse Berlin vs. THW Kiel",
            "BR Volleys vs. SV Warnemünde",
            "Alba Berlin vs. SC Rasta Vechta",
            "DHB-Pokal Final Four",
            "Harlem Globetrotters RIVALRY TOUR",
        ):
            self.assertEqual(main.categorize_event(titel), f"Sport: {titel}")

    def test_konzert(self):
        for titel in (
            "berq Tour 2026",
            "Blok3 Arena Live Tour 2026/27",
            "Weihnachtskonzert",
            "Die große Abschiedstour",
        ):
            self.assertEqual(main.categorize_event(titel), f"Konzert: {titel}")

    def test_keine_falschen_treffer_durch_teilwoerter(self):
        # Früher: "Oliver" enthält "live", "Tournament" enthält "tour".
        for titel in ("Oliver Pocher", "Tournament of Magic", "Berlin Tattoo"):
            self.assertEqual(main.categorize_event(titel), f"Event: {titel}")


class NachrichtenTest(unittest.TestCase):
    def test_mehrere_vorstellungen_am_tag_ergeben_eine_nachricht(self):
        tag = date(2026, 11, 7)
        [nachricht] = main.build_day_notifications(events(), tag, today=tag)
        self.assertEqual(nachricht.title, "Event: Berlin Tattoo")
        self.assertIn("Heute: 07.11.2026", nachricht.body)
        self.assertIn("Beginn: 13:30 & 19:00 Uhr", nachricht.body)
        self.assertEqual(nachricht.click, "https://tickets.example/tattoo-mittag")

    def test_statushinweis_landet_in_titel_und_text(self):
        tag = date(2026, 11, 27)
        [nachricht] = main.build_day_notifications(events(), tag, today=tag)
        self.assertEqual(nachricht.title, "⚠️ Konzert: RIN Nostalgia Tour")
        self.assertIn("Laut Website: verschoben", nachricht.body)

    def test_freier_tag_ergibt_keine_nachricht(self):
        tag = date(2026, 11, 15)
        self.assertEqual(main.build_day_notifications(events(), tag, today=tag), [])


class AblaufTest(unittest.TestCase):
    def pruefe(self, tag):
        gesendet = []
        with (
            mock.patch.object(main, "fetch_events", return_value=events()),
            redirect_stdout(io.StringIO()),
        ):
            main.check_events(tag, None, gesendet.append, today=tag)
        return [nachricht.title for nachricht in gesendet]

    def test_samstag_mit_spiel(self):
        self.assertEqual(
            self.pruefe(date(2026, 11, 14)),
            ["Sport: Füchse Berlin vs. THW Kiel Handball-Bundesliga 2026/27"],
        )

    def test_freier_tag_sendet_nichts(self):
        self.assertEqual(self.pruefe(date(2026, 11, 9)), [])

    def test_seite_ohne_erkennbare_termine_ist_ein_fehler(self):
        session = mock.Mock()
        session.get.return_value = mock.Mock(
            content=b"<html><body>Wartungsarbeiten</body></html>", url=main.URL
        )
        with self.assertRaises(RuntimeError):
            main.fetch_events(session)

    def test_trockenlauf_sendet_nichts(self):
        with (
            mock.patch.object(main, "fetch_events", return_value=events()),
            mock.patch.object(main, "send_notification") as senden,
            redirect_stdout(io.StringIO()) as ausgabe,
        ):
            main.main(["--dry-run", "--datum", "2026-11-14"])
        senden.assert_not_called()
        self.assertIn(
            "[Trockenlauf] Würde senden: Sport: Füchse Berlin", ausgabe.getvalue()
        )

    def test_fehler_wird_gemeldet_und_weitergereicht(self):
        actions_umgebung = {
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_REPOSITORY": "MaxNode21/max-schmeling-halle-warner",
            "GITHUB_RUN_ID": "42",
        }
        with (
            mock.patch.object(main, "fetch_events", side_effect=RuntimeError("kaputt")),
            mock.patch.object(main, "send_notification") as senden,
            mock.patch.dict(os.environ, actions_umgebung),
            redirect_stdout(io.StringIO()),
            self.assertRaises(RuntimeError),
        ):
            main.main(["--datum", "2026-11-14"])

        senden.assert_called_once()
        nachricht = senden.call_args.args[1]
        self.assertEqual(nachricht.title, "Max-Schmeling-Halle: Skriptfehler")
        self.assertEqual(nachricht.body, "RuntimeError: kaputt")
        self.assertEqual(
            nachricht.click,
            "https://github.com/MaxNode21/max-schmeling-halle-warner/actions/runs/42",
        )


class NtfyTest(unittest.TestCase):
    def test_nachricht_wird_als_json_verschickt(self):
        session = mock.Mock()
        main.send_notification(session, main.Notification("Titel", "Text"))

        session.post.assert_called_once()
        self.assertEqual(session.post.call_args.args[0], "https://ntfy.sh/")
        self.assertEqual(
            session.post.call_args.kwargs["json"],
            {
                "topic": "max-schmeling-halle-warner",
                "title": "Titel",
                "message": "Text",
                "priority": 4,
                "tags": ["ticket"],
                "click": main.URL,
            },
        )


if __name__ == "__main__":
    unittest.main()
