#!/usr/bin/env python3
"""
Automatischer Spritpreis-Tracker
Scrappt Spritpreise von ich-tanke.de mit Selenium (JavaScript-Support)
"""

import csv
import os
import re
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# Konfiguration
CSV_FILE = "prices.csv"
CSV_HEADER = ["time", "price"]

# Tankstelle: ich-tanke.de
TARGET_URL = "https://ich-tanke.de/tankstelle/67a2fe58c42fd7cbe5fe8fa7f515b70b/"
# Fuel type zu tracken: "Super Benzin" oder "Super (E10)" oder "Diesel"
FUEL_TYPE = "Super (E10) Benzin"
# XPath zum Finden von Preisinformationen auf der Seite
PRICE_XPATH_PATTERNS = [
    "//span[contains(., 'E10')]/../following-sibling::*[contains(., '.')]",
    "//span[contains(text(), 'E10')]/parent::*/following-sibling::*/text()",
    "//*[contains(text(), '1.')]",
]


def init_csv_if_needed():
    """
    Erstellt die CSV-Datei mit Header falls sie nicht existiert.
    """
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)
        print(f"[+] CSV-Datei '{CSV_FILE}' erstellt mit Header: {CSV_HEADER}")


def get_fuel_price():
    """
    Scrappt den aktuellen Spritpreis von ich-tanke.de mit Selenium.
    Lädt JavaScript dynamisch und extrahiert den Preis mit Regex.

    Returns:
        str: Der gescrapte Preis (z.B. "1.939") oder None falls fehlgeschlagen
    """
    driver = None
    try:
        # Chrome im headless Modus starten (für GitHub Actions)
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        driver.set_page_load_timeout(15)

        print("[*] Lade Seite mit Selenium...")
        driver.get(TARGET_URL)

        # Warte bis die Seite vollständig geladen ist (max. 10 Sekunden)
        time.sleep(3)
        WebDriverWait(driver, 10).until(
            lambda d: len(d.find_elements(By.TAG_NAME, "span")) > 20
        )

        # Hole den kompletten Seiten-Text
        page_text = driver.page_source

        # Suche nach E10/Super (E10) Preis mit Regex
        # Pattern: Suche nach "E10" oder "Super (E10)" gefolgt von einer Zahl wie "1.939"
        price_match = re.search(
            r'(?:E10|Super\s*\(E10\))[^0-9]*?(\d+\.\d{3})',
            page_text,
            re.IGNORECASE
        )

        if not price_match:
            # Versuche allgemeines Preismuster
            price_match = re.search(r'([1-2]\.\d{3})', page_text)

        if price_match:
            price = price_match.group(1)
            return price

        print(f"[!] Konnte Preis für '{FUEL_TYPE}' nicht finden")
        return None

    except Exception as e:
        print(f"[-] Fehler beim Scrapen: {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


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
        print(f"[!] Fehler beim Lesen der CSV: {e}")

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

        print(f"[+] Preis gespeichert: {price} Euro um {now}")
        return True

    except Exception as e:
        print(f"[-] Fehler beim Speichern: {e}")
        return False


def main():
    """
    Hauptfunktion: Initialisiert CSV, scrappt Preis, speichert ihn.
    """
    print("=" * 50)
    print("Spritpreis-Tracker - Ausführung")
    print("=" * 50)
    print(f"Trackiere: {FUEL_TYPE}")
    print(f"Quelle: ich-tanke.de")

    # Schritt 1: CSV initialisieren falls nötig
    init_csv_if_needed()

    # Schritt 2: Aktuellen Preis scrapen
    print("\n[*] Scrappt aktuellen Preis...")
    price = get_fuel_price()

    if not price:
        print("[-] Konnte keinen Preis scrapen. Abbruch.")
        return False

    print(f"\n[+] Aktueller Preis: {price} Euro")

    # Schritt 3: Prüfe ob Preis bereits gespeichert wurde (Duplikate vermeiden)
    if price_already_recorded(price):
        print("[*] Dieser Preis wurde bereits kürzlich gespeichert. Keine Änderung.")
        return True

    # Schritt 4: Neuen Preis speichern
    print("\n[*] Speichere Preis...")
    return save_price(price)


if __name__ == "__main__":
    success = main()
    print("=" * 50)
    exit(0 if success else 1)
