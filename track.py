#!/usr/bin/env python3
"""
Automatischer Spritpreis-Tracker
Scrappt Spritpreise (E10 und Diesel) von ich-tanke.de mit Selenium (JavaScript-Support)
"""

import csv
import os
import re
import time
from datetime import datetime, timezone, timedelta

# Konfiguration - Tankstelle
TARGET_URL = "https://ich-tanke.de/tankstelle/67a2fe58c42fd7cbe5fe8fa7f515b70b/"

# Zeitzone: CET (UTC+1)
CET = timezone(timedelta(hours=1))

# Treibstoffe zu tracken mit jeweils CSV-Datei
FUEL_TYPES = {
    "E10": {
        "csv_file": "e10_prices.csv",
        "patterns": [
            r'(?:E10|Super\s*\(E10\))[^0-9]*?(\d+\.\d{3})',
        ]
    },
    "Diesel": {
        "csv_file": "diesel_prices.csv",
        "patterns": [
            r'Diesel[^0-9]*?(\d+\.\d{3})',
            r'(?:Dieselpreis|diesel)[^0-9]*?(\d+\.\d{3})',
        ]
    }
}

CSV_HEADER = ["time", "price"]


def init_csv_if_needed(fuel_type):
    """
    Erstellt die CSV-Datei mit Header falls sie nicht existiert.

    Args:
        fuel_type (str): "E10" oder "Diesel"
    """
    csv_file = FUEL_TYPES[fuel_type]["csv_file"]

    if not os.path.exists(csv_file):
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)
        print(f"[+] CSV-Datei '{csv_file}' erstellt mit Header: {CSV_HEADER}")


def get_current_cet_time():
    """
    Gibt aktuelle Zeit in CET (UTC+1) zurück.

    Returns:
        str: Zeit im Format "YYYY-MM-DD HH:MM:SS"
    """
    now_utc = datetime.now(timezone.utc)
    now_cet = now_utc.astimezone(CET)
    return now_cet.strftime("%Y-%m-%d %H:%M:%S")


def get_fuel_prices():
    """
    Scrappt alle konfigurierten Spritpreise von ich-tanke.de.
    Versucht zuerst Selenium, fällt auf requests+BeautifulSoup zurück.

    Returns:
        dict: {"E10": "1.939", "Diesel": "2.119"} oder teilweise gefüllt
    """
    # Versuche zuerst mit Selenium (für lokale Nutzung)
    prices = try_selenium_scrape()

    if prices:
        return prices

    # Fallback auf einfaches Scraping (für GitHub Actions)
    print("[*] Selenium fehlgeschlagen, nutze Fallback-Methode...")
    return try_simple_scrape()


def try_selenium_scrape():
    """Versucht zu scrapen mit Selenium."""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service

        driver = None
        prices = {}

        # Chrome im headless Modus starten
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

        try:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            driver.set_page_load_timeout(15)

            print("[*] Lade Seite mit Selenium...")
            driver.get(TARGET_URL)

            time.sleep(3)
            WebDriverWait(driver, 10).until(
                lambda d: len(d.find_elements(By.TAG_NAME, "span")) > 20
            )

            page_text = driver.page_source

            # Suche nach Preisen
            for fuel_type, config in FUEL_TYPES.items():
                price = None
                for pattern in config["patterns"]:
                    price_match = re.search(pattern, page_text, re.IGNORECASE)
                    if price_match:
                        price = price_match.group(1)
                        break

                if not price:
                    price_match = re.search(r'([1-3]\.\d{3})', page_text)
                    if price_match:
                        price = price_match.group(1)

                if price:
                    prices[fuel_type] = price

            return prices

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    except Exception as e:
        print(f"[!] Selenium fehlgeschlagen: {e}")
        return {}


def try_simple_scrape():
    """Fallback: Einfaches Scraping mit requests + BeautifulSoup."""
    try:
        import requests
        from bs4 import BeautifulSoup

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        print("[*] Lade Seite mit requests...")
        response = requests.get(TARGET_URL, timeout=10, headers=headers)
        response.raise_for_status()

        page_text = response.text
        prices = {}

        # Suche nach Preisen im HTML-Text
        for fuel_type, config in FUEL_TYPES.items():
            price = None
            for pattern in config["patterns"]:
                price_match = re.search(pattern, page_text, re.IGNORECASE)
                if price_match:
                    price = price_match.group(1)
                    break

            if not price:
                price_match = re.search(r'([1-3]\.\d{3})', page_text)
                if price_match:
                    price = price_match.group(1)

            if price:
                prices[fuel_type] = price

        return prices

    except Exception as e:
        print(f"[-] Einfaches Scraping fehlgeschlagen: {e}")
        return {}


def price_already_recorded(fuel_type, price):
    """
    Prüft ob der aktuelle Preis bereits in den letzten Einträgen vorhanden ist.
    Das verhindert, dass identische Preise mehrfach hintereinander gespeichert werden.

    Args:
        fuel_type (str): "E10" oder "Diesel"
        price (str): Der zu prüfende Preis

    Returns:
        bool: True falls Preis bereits vorhanden, False sonst
    """
    csv_file = FUEL_TYPES[fuel_type]["csv_file"]

    if not os.path.exists(csv_file):
        return False

    try:
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            # Prüfe die letzten Einträge (letzte 5)
            if rows:
                for row in rows[-5:]:
                    if row.get("price") == price:
                        return True
    except Exception as e:
        print(f"[!] Fehler beim Lesen der CSV für '{fuel_type}': {e}")

    return False


def save_price(fuel_type, price):
    """
    Speichert den Preis mit aktuellem Zeitstempel (CET) in die entsprechende CSV.

    Args:
        fuel_type (str): "E10" oder "Diesel"
        price (str): Der zu speichernde Preis

    Returns:
        bool: True falls erfolgreich gespeichert, False sonst
    """
    csv_file = FUEL_TYPES[fuel_type]["csv_file"]

    try:
        now = get_current_cet_time()

        # CSV-Datei muss zu diesem Punkt existieren (wurde in init_csv_if_needed erstellt)
        with open(csv_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([now, price])

        print(f"[+] {fuel_type}-Preis gespeichert: {price} Euro um {now} CET")
        return True

    except Exception as e:
        print(f"[-] Fehler beim Speichern {fuel_type}-Preis: {e}")
        return False


def main():
    """
    Hauptfunktion: Initialisiert CSVs, scrappt Preise, speichert sie.
    """
    print("=" * 50)
    print("Spritpreis-Tracker - Ausführung")
    print("=" * 50)
    print(f"Quelle: ich-tanke.de")
    print(f"Zeitzone: CET (UTC+1)")

    # Schritt 1: CSVs initialisieren falls nötig
    for fuel_type in FUEL_TYPES.keys():
        init_csv_if_needed(fuel_type)

    # Schritt 2: Aktuelle Preise scrapen
    print("\n[*] Scrappt aktuelle Preise...")
    prices = get_fuel_prices()

    if not prices:
        print("[-] Konnte keine Preise scrapen. Abbruch.")
        return False

    # Schritt 3: Preise speichern (nur wenn neu)
    success = True
    for fuel_type, price in prices.items():
        print(f"\n[+] Aktueller Preis {fuel_type}: {price} Euro")

        # Prüfe ob Preis bereits gespeichert wurde (Duplikate vermeiden)
        if price_already_recorded(fuel_type, price):
            print(f"[*] Dieser {fuel_type}-Preis wurde bereits kürzlich gespeichert. Keine Änderung.")
            continue

        # Neuen Preis speichern
        print(f"[*] Speichere {fuel_type}-Preis...")
        if not save_price(fuel_type, price):
            success = False

    return success


if __name__ == "__main__":
    success = main()
    print("=" * 50)
    exit(0 if success else 1)
