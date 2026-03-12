#!/usr/bin/env python3
"""
Automatischer Spritpreis-Tracker
Scrappt Spritpreise von einer Tankstellen-Webseite und speichert sie in prices.csv
"""

import csv
import os
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# Konfiguration
CSV_FILE = "prices.csv"
CSV_HEADER = ["time", "price"]

# Beispiel-URL - diese muss angepasst werden wenn tatsächlich ein echter Service genutzt wird
# Für Demo verwenden wir eine Test-URL
TARGET_URL = "https://www.example.com"
PRICE_SELECTOR = ".price"


def init_csv_if_needed():
    """
    Erstellt die CSV-Datei mit Header falls sie nicht existiert.
    """
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)
        print(f"✓ CSV-Datei '{CSV_FILE}' erstellt mit Header: {CSV_HEADER}")


def get_fuel_price():
    """
    Scrappt den aktuellen Spritpreis von der konfigurierten Webseite.

    Returns:
        str: Der gescrapte Preis (z.B. "1.85") oder None falls fehlgeschlagen
    """
    try:
        # HTTP-Request mit Timeout
        response = requests.get(TARGET_URL, timeout=10)
        response.raise_for_status()

        # HTML parsen
        soup = BeautifulSoup(response.content, "html.parser")

        # Preis mit dem konfigurierten CSS-Selektor suchen
        price_element = soup.select_one(PRICE_SELECTOR)

        if not price_element:
            print(f"⚠ Preis-Element nicht gefunden (Selektor: {PRICE_SELECTOR})")
            return None

        price_text = price_element.get_text(strip=True)

        # Extrahiere nur die Zahl (entferne € Symbol, Leerzeichen etc.)
        price_clean = "".join(c for c in price_text if c.isdigit() or c == ".")

        if price_clean:
            return price_clean
        else:
            print(f"⚠ Konnte Preis nicht parsen: {price_text}")
            return None

    except requests.RequestException as e:
        print(f"✗ Fehler beim HTTP-Request: {e}")
        return None
    except Exception as e:
        print(f"✗ Fehler beim Scrapen: {e}")
        return None


def price_already_recorded(price):
    """
    Prüft ob der aktuelle Preis bereits in den letzten Einträgen vorhanden ist.
    Das verhindert, dass identische Preise mehrfach hintereinander gespeichert werden.

    Args:
        price (str): Der zu prüfende Preis

    Returns:
        bool: True falls Preis bereits vorhanden, False sonst
    """
    if not os.path.exists(CSV_FILE):
        return False

    try:
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            # Prüfe die letzten Einträge (letzte 5)
            if rows:
                for row in rows[-5:]:
                    if row.get("price") == price:
                        return True
    except Exception as e:
        print(f"⚠ Fehler beim Lesen der CSV: {e}")

    return False


def save_price(price):
    """
    Speichert den Preis mit aktuellem Zeitstempel in prices.csv.

    Args:
        price (str): Der zu speichernde Preis

    Returns:
        bool: True falls erfolgreich gespeichert, False sonst
    """
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # CSV-Datei muss zu diesem Punkt existieren (wurde in init_csv_if_needed erstellt)
        with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([now, price])

        print(f"✓ Preis gespeichert: {price} € um {now}")
        return True

    except Exception as e:
        print(f"✗ Fehler beim Speichern: {e}")
        return False


def main():
    """
    Hauptfunktion: Initialisiert CSV, scrappt Preis, speichert ihn.
    """
    print("=" * 50)
    print("Spritpreis-Tracker - Ausführung")
    print("=" * 50)

    # Schritt 1: CSV initialisieren falls nötig
    init_csv_if_needed()

    # Schritt 2: Aktuellen Preis scrapen
    print("\n📍 Scrappt aktuellen Preis...")
    price = get_fuel_price()

    if not price:
        print("✗ Konnte keinen Preis scrapen. Abbruch.")
        return False

    print(f"\n💰 Aktueller Preis: {price} €")

    # Schritt 3: Prüfe ob Preis bereits gespeichert wurde (Duplikate vermeiden)
    if price_already_recorded(price):
        print("ℹ Dieser Preis wurde bereits kürzlich gespeichert. Keine Änderung.")
        return True

    # Schritt 4: Neuen Preis speichern
    print("\n💾 Speichere Preis...")
    return save_price(price)


if __name__ == "__main__":
    success = main()
    print("=" * 50)
    exit(0 if success else 1)
