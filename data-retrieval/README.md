# Provider Contact Scraper

Kuratierte Liste medizinischer Anbieter (DEXA-Scan / Body-Composition) mit Kontakt- und Geodaten.

## Setup

```bash
cp .env.example .env        # API-Keys eintragen
pip install -r requirements.txt
```

## Pipeline

### Stufe 1: Scrape

```bash
python scripts/scrape_providers.py --input data/bodycomp_provider_url.json --output output/bodycomp_providers.json
```

### Stufe 2: Geocode

```bash
python scripts/geocode_providers.py output/bodycomp_providers.json
```

Optionen:
- `--force` — bereits geocodete Records neu auflösen
- `--cache data/geocode_cache.json` — Cache-Pfad (Default)

### Validierung

```bash
python -m jsonschema -i output/bodycomp_providers.json data/providers.schema.json
```
