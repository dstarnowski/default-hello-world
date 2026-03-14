# Scraper uchwał Rady Dzielnicy XI Podgórze Duchackie

Skrypt pobiera wszystkie uchwały Rady Dzielnicy XI Podgórze Duchackie w Krakowie
ze strony [BIP Miasta Krakowa](https://www.bip.krakow.pl/?dok_id=48955) i zapisuje
je jako pliki PDF do wskazanego katalogu lokalnego.

Pokrywa wszystkie dostępne kadencje (6.–9.) i lata (2012–obecnie), łącznie ok. 1400+ dokumentów.

---

## Wymagania

- Python 3.10+
- Biblioteki: `requests`, `beautifulsoup4`, `lxml`

```bash
pip install -r requirements.txt
```

---

## Użycie

```bash
python scrape_uchwaly.py [opcje]
```

### Opcje

| Opcja | Domyślnie | Opis |
|---|---|---|
| `-o`, `--output DIR` | `uchwaly_dzielnica_xi` | Katalog, do którego zapisywane są pliki PDF |
| `--delay SEKUNDY` | `0.5` | Przerwa między żądaniami HTTP (s) |
| `--dry-run` | — | Wyświetla listę plików bez pobierania |

### Przykłady

```bash
# Pobierz wszystko do domyślnego katalogu ./uchwaly_dzielnica_xi/
python scrape_uchwaly.py

# Własny katalog docelowy
python scrape_uchwaly.py -o /ścieżka/do/katalogu/

# Podgląd — pokaż co by zostało pobrane, bez rzeczywistego pobierania
python scrape_uchwaly.py --dry-run

# Wolniejsze pobieranie (grzeczniejsze dla serwera)
python scrape_uchwaly.py --delay 1.0
```

---

## Nazewnictwo plików

Każdy plik PDF otrzymuje nazwę opartą na numerze uchwały, np.:

```
XXVI_270_2025.pdf    ← uchwała nr XXVI/270/2025
IX_112_2024.pdf      ← uchwała nr IX/112/2024
XIV_126_2012.pdf     ← uchwała nr XIV/126/2012
```

---

## Wznawianie pobierania

Skrypt sprawdza, czy plik już istnieje, i pomija go — można więc bezpiecznie przerwać
i wznowić pobieranie w dowolnym momencie bez pobierania tych samych plików ponownie.

---

## Jak działa

1. Pobiera stronę indeksu uchwał i wykrywa wszystkie dostępne strony roczne.
2. Dla każdego roku parsuje tabelę uchwał i wyciąga identyfikatory dokumentów.
3. Dla każdej uchwały konstruuje bezpośredni URL do pliku PDF i go pobiera.

Przy błędach sieciowych skrypt automatycznie ponawia próbę (do 3 razy,
z opóźnieniem 2 s / 4 s / 8 s).

---

## Źródło danych

- Strona główna: [BIP Kraków – Uchwały Rady Dzielnicy XI](https://www.bip.krakow.pl/?dok_id=48955)
- Obejmuje kadencje: 6. (2012–2014), 7. (2014–2018), 8. (2018–2023), 9. (2023–)
