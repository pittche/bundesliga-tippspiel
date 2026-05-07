#!/usr/bin/env python3
"""
Bundesliga Tippspiel - Einfacher Starter

Nutzung:
    python tippspiel.py           # Zeigt Hilfe
    python tippspiel.py init      # Erstmalige Einrichtung
    python tippspiel.py update    # Daten aktualisieren
    python tippspiel.py predict   # Prognosen anzeigen
    python tippspiel.py table     # Tabelle anzeigen
    python tippspiel.py all       # Alles zusammen
"""

import sys
from pathlib import Path

# Source-Verzeichnis zum Pfad hinzufuegen
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from tippspiel.app import TippspielApp


def print_header():
    print("""
============================================================

    BUNDESLIGA TIPPSPIEL

    Kostenlose Prognosen mit Elo + xG + Sentiment

============================================================
    """)


def print_help():
    print("""
Verfuegbare Befehle:

  init      Datenbank erstmalig einrichten (nur einmal noetig)
  update    Aktuelle Daten laden (Ergebnisse, xG, News)
  predict   Prognosen fuer kommende Spiele anzeigen
  table     Aktuelle Tabelle mit Elo-Ratings
  all       Alles zusammen (init + update + predict + table)

Beispiel:
  python tippspiel.py all

Tipp: Fuehre 'update' regelmaessig aus (z.B. am Spieltag-Morgen)
      um aktuelle Daten zu haben.
    """)


def main():
    print_header()

    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()

    # DB-Pfad: Benutzerverzeichnis oder Temp (WSL-Netzwerkpfade funktionieren nicht)
    import platform

    if platform.system() == "Windows":
        # Auf Windows: User-Verzeichnis
        user_home = Path.home()
        db_dir = user_home / ".tippspiel"
        db_dir.mkdir(exist_ok=True)
        db_path = db_dir / "tippspiel.db"
    else:
        # Auf Linux/Mac: im Projektverzeichnis
        db_path = Path(__file__).parent / "tippspiel.db"

    print(f"Datenbank: {db_path}\n")
    app = TippspielApp(db_path=str(db_path), season="2025")

    try:
        if command == "init":
            print("[*] Initialisiere Datenbank...\n")
            app.initialize()
            print("\n[OK] Fertig! Fuehre jetzt 'python tippspiel.py update' aus.")

        elif command == "update":
            print("[*] Aktualisiere Daten...\n")
            app.update_all(verbose=True)
            print("\n[OK] Daten aktualisiert!")

        elif command == "predict":
            predictions = app.get_predictions()
            if predictions:
                app.print_predictions(predictions)
            else:
                print("[!] Keine anstehenden Spiele gefunden.")
                print("    Tipp: Fuehre zuerst 'python tippspiel.py update' aus.")

        elif command == "table":
            app.print_table()

        elif command == "all":
            print("[*] Vollstaendiger Durchlauf...\n")
            app.initialize()
            app.update_all(verbose=True)

            print("\n" + "="*60)
            predictions = app.get_predictions()
            if predictions:
                app.print_predictions(predictions)
            else:
                print("\nKeine anstehenden Spiele.")

            app.print_table()
            print("\n[OK] Alles fertig!")

        elif command == "help" or command == "-h" or command == "--help":
            print_help()

        else:
            print(f"[!] Unbekannter Befehl: {command}")
            print_help()

    except KeyboardInterrupt:
        print("\n\n[!] Abgebrochen.")

    except Exception as e:
        print(f"\n[ERROR] Fehler: {e}")
        print("\nFalls das Problem weiterhin besteht:")
        print("1. Pruefe deine Internetverbindung")
        print("2. Loesche die DB und starte mit 'init' neu")


if __name__ == "__main__":
    main()
