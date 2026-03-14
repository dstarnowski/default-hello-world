#!/usr/bin/env python3
"""
Skrypt pobiera wszystkie uchwały Rady Dzielnicy XI Podgórze Duchackie
ze strony BIP Miasta Krakowa (bip.krakow.pl) i zapisuje je jako PDF
do wskazanego katalogu.

Użycie:
    python scrape_uchwaly.py                  # pobiera do ./uchwaly_dzielnica_xi/
    python scrape_uchwaly.py -o /ścieżka/     # własny katalog docelowy
    python scrape_uchwaly.py --delay 1.0      # wolniejsze pobieranie (s)
    python scrape_uchwaly.py --dry-run        # tylko pokazuje co by pobrał
"""

import os
import re
import sys
import time
import argparse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.bip.krakow.pl"
INDEX_URL = f"{BASE_URL}/?dok_id=48955"  # Zbiorcza lista uchwał Rady Dzielnicy XI
DEFAULT_OUTPUT_DIR = "uchwaly_dzielnica_xi"
DEFAULT_DELAY = 0.5  # sekundy między żądaniami HTTP

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
})


def get_page(url: str, retries: int = 3) -> BeautifulSoup | None:
    """Pobiera stronę i zwraca obiekt BeautifulSoup."""
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.content, "html.parser")
        except requests.RequestException as e:
            wait = 2 ** attempt
            print(f"  [błąd HTTP] {url}: {e}", file=sys.stderr)
            if attempt < retries - 1:
                print(f"  Ponowna próba za {wait}s…", file=sys.stderr)
                time.sleep(wait)
    return None


def get_year_page_links(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """
    Ze strony indeksu wyciąga linki do stron rocznych.
    Filtruje tylko linki z ?dok_id=LICZBA (bez innych parametrów)
    i pomija sam indeks (dok_id=48955).
    """
    INDEX_DOK_ID = "48955"
    seen = set()
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        m = re.fullmatch(r"\?dok_id=(\d+)", href)
        if not m:
            continue
        dok_id = m.group(1)
        if dok_id == INDEX_DOK_ID or dok_id in seen:
            continue
        seen.add(dok_id)
        label = a.get_text(strip=True) or dok_id
        full_url = f"{BASE_URL}/{href}"
        links.append((label, full_url))

    return links


def parse_resolutions(soup: BeautifulSoup) -> list[dict]:
    """
    Ze strony rocznej wyciąga listę uchwał.
    Każda uchwała to słownik z kluczami: number, date, subject, doc_id, pdf_url.
    """
    resolutions = []
    table = soup.find("table")
    if not table:
        return resolutions

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        # Szukaj linku do karty dokumentu w ostatniej kolumnie
        karta_link = None
        for a in cells[-1].find_all("a", href=True):
            if "/zalaczniki/dokumenty/n/" in a["href"]:
                karta_link = a["href"]
                break
        if not karta_link:
            continue

        m = re.search(r"/zalaczniki/dokumenty/n/(\d+)/karta", karta_link)
        if not m:
            continue
        doc_id = m.group(1)

        resolutions.append({
            "session":  cells[0].get_text(strip=True),
            "date":     cells[1].get_text(strip=True),
            "number":   cells[2].get_text(strip=True),
            "subject":  cells[3].get_text(strip=True),
            "doc_id":   doc_id,
            "pdf_url":  f"{BASE_URL}/plik.php?zid={doc_id}&wer=0&new=t&mode=shw",
        })

    return resolutions


def make_filename(res: dict) -> str:
    """
    Tworzy nazwę pliku na podstawie numeru uchwały.
    Np. 'XXVI_270_2025.pdf'  (znaki / zamieniane na _)
    """
    safe = re.sub(r"[^\w\-.]", "_", res["number"].replace("/", "_")).strip("_")
    return f"{safe}.pdf" if safe else f"doc_{res['doc_id']}.pdf"


def download_pdf(url: str, filepath: Path, retries: int = 3) -> bool:
    """Pobiera plik PDF i zapisuje go pod podaną ścieżką."""
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=60, stream=True)
            resp.raise_for_status()

            ctype = resp.headers.get("content-type", "")
            if "html" in ctype:
                # Strona błędu zamiast PDF
                print(f"  [ostrzeżenie] Odpowiedź HTML zamiast PDF: {url}", file=sys.stderr)
                return False

            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=16384):
                    f.write(chunk)
            return True

        except requests.RequestException as e:
            wait = 2 ** attempt
            print(f"  [błąd pobierania] {url}: {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(wait)
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Pobiera uchwały Rady Dzielnicy XI Podgórze Duchackie z BIP Kraków"
    )
    parser.add_argument(
        "-o", "--output",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Katalog docelowy (domyślnie: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Opóźnienie między żądaniami w sekundach (domyślnie: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Tylko wyświetl co by zostało pobrane, bez rzeczywistego pobierania",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    if not args.dry_run:
        output_path.mkdir(parents=True, exist_ok=True)
        print(f"Katalog docelowy: {output_path.resolve()}")

    # Krok 1: Pobierz stronę indeksu i znajdź linki do stron rocznych
    print(f"\nPobieranie indeksu uchwał: {INDEX_URL}")
    index_soup = get_page(INDEX_URL)
    if not index_soup:
        print("BŁĄD: Nie można pobrać strony indeksu.", file=sys.stderr)
        sys.exit(1)

    year_links = get_year_page_links(index_soup)
    if not year_links:
        print("BŁĄD: Nie znaleziono żadnych linków do stron rocznych.", file=sys.stderr)
        sys.exit(1)

    print(f"Znaleziono {len(year_links)} stron rocznych:")
    for label, url in year_links:
        print(f"  {label:20s}  {url}")

    # Krok 2: Dla każdego roku pobierz listę uchwał i ściągnij PDF-y
    total_downloaded = 0
    total_skipped = 0
    total_errors = 0

    for label, url in year_links:
        print(f"\n{'='*60}")
        print(f"  Rok/okres: {label}  ({url})")
        print(f"{'='*60}")

        time.sleep(args.delay)
        year_soup = get_page(url)
        if not year_soup:
            print(f"  [pomiń] Nie można pobrać strony.", file=sys.stderr)
            continue

        resolutions = parse_resolutions(year_soup)
        if not resolutions:
            print(f"  Brak uchwał lub nieznana struktura tabeli.")
            continue

        print(f"  Znaleziono {len(resolutions)} uchwał")

        for res in resolutions:
            filename = make_filename(res)
            filepath = output_path / filename

            if args.dry_run:
                print(f"  [dry-run] {filename}  ←  {res['pdf_url']}")
                total_downloaded += 1
                continue

            if filepath.exists():
                print(f"  [pomiń]   {filename}  (już istnieje)")
                total_skipped += 1
                continue

            print(f"  [pobierz] {res['number']:25s}  {res['date']}  {res['subject'][:50]}")
            time.sleep(args.delay)

            if download_pdf(res["pdf_url"], filepath):
                total_downloaded += 1
            else:
                total_errors += 1

    print(f"\n{'='*60}")
    print(f"  PODSUMOWANIE")
    print(f"{'='*60}")
    if args.dry_run:
        print(f"  Do pobrania: {total_downloaded} plików (tryb dry-run)")
    else:
        print(f"  Pobrano:     {total_downloaded}")
        print(f"  Pominięto:   {total_skipped}  (pliki już istniały)")
        print(f"  Błędy:       {total_errors}")
        print(f"  Katalog:     {output_path.resolve()}")


if __name__ == "__main__":
    main()
