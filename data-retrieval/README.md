# Daten-Pipeline: Provider-Scraping und Geocoding

Dieses Subprojekt erzeugt die Seed-Daten für die interaktive Karte — kuratierte Listen von DEXA-Body-Composition-Anbietern und Selbstzahler-Blutlaboren im DACH-Raum. Den vollständigen Systemkontext (Backend, Frontend, Docker-Setup) findest du im [Root-README](../README.md).

## Voraussetzungen

- Python 3.10+
- Ein [Firecrawl-Account](https://www.firecrawl.dev) mit aktivem API-Key

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
cp .env.example .env
pip install -r requirements.txt
```

`.env`-Felder:

| Variable | Beschreibung | Bezug |
|---|---|---|
| `FIRECRAWL_API_KEY` | API-Key für Firecrawl | [firecrawl.dev/app](https://www.firecrawl.dev/app) |
| `NOMINATIM_USER_AGENT` | Pflicht-Header für Nominatim, z. B. `MeinProjekt/1.0 (mail@example.de)` | Selbst wählen |

**Hinweis:** Die `output/`-Dateien enthalten bereits manuell verifizierten Datensatz. Ein erneuter Scrape-Lauf überschreibt diese Daten mit rohen Ergebnissen.

---

## Pipeline

### Stufe 1: Scrape

Extrahiert Kontaktdaten aus den Provider-URLs via Firecrawl.

**DEXA / Body-Composition-Anbieter:**
```bash
python scripts/scrape_providers.py \
  --input data/bodycomp_provider_url.json \
  --output output/bodycomp_providers.json
```

**Selbstzahler-Blutlabore:**
```bash
python scripts/scrape_providers.py \
  --input data/blood_provider_url.json \
  --output output/blood_providers.json
```

Einträge mit leerem `name`- oder `url`-Feld werden übersprungen. Unvollständige Records landen in `output/*.errors.json`.

---

### Stufe 2: Geocode

Löst Adressen zu WGS84-Koordinaten auf (Nominatim, 1 req/sec). Bereits geocodete Records bleiben unberührt.

```bash
python scripts/geocode_providers.py output/bodycomp_providers.json
python scripts/geocode_providers.py output/blood_providers.json
```

Optionen:
- `--force` — bereits geocodete Records neu auflösen
- `--cache data/geocode_cache.json` — Cache-Pfad (Default)

Fehlgeschlagene Geocodes landen in `output/*.geocode-errors.json`. Der Cache (`data/geocode_cache.json`) verhindert wiederholte API-Calls für dieselben Adressen.

---

### Stufe 3: Manuelle Verifikation

Die automatisierten Schritte liefern Rohkontaktdaten. Vor dem Einsatz im Backend jeden Eintrag prüfen:

- DEXA-Anbieter: bietet die Praxis **Body Composition** an (nicht nur Knochendichte)?
- Blutlabor: ist eine Untersuchung **ohne ärztliche Überweisung** möglich?
- Preise und Besonderheiten ergänzen, falls öffentlich verfügbar

---

### Stufe 4: Validierung

```bash
python -m jsonschema -i output/bodycomp_providers.json data/providers.schema.json
python -m jsonschema -i output/blood_providers.json data/providers.schema.json
```

---

## Output-Format

Beide Output-Dateien sind JSON-Arrays gemäß `data/providers.schema.json`. Ein Beispiel-Record ist in `data/providers.template.json` hinterlegt.

| Feld | Typ | Beschreibung |
|---|---|---|
| `name` | string | Name der Praxis / des Labors |
| `street` | string | Straße und Hausnummer |
| `postal_code` | string | Postleitzahl |
| `city` | string | Ort |
| `country` | string | ISO 3166-1 alpha-2 (`DE`, `AT`, `CH`) |
| `latitude` / `longitude` | number \| null | WGS84-Koordinaten |
| `phone` | string \| null | Internationales Format (`+49 511 …`), sonst `null` |
| `email` | string \| null | Öffentliche Kontaktadresse, sonst `null` |
| `website` | string \| null | Homepage-URL, sonst `null` |
| `source_url` | string | URL der verifizierten Quellseite |
| `verified_at` | string | ISO-8601-Timestamp des letzten Scrapes |
| `services` | array | Reserviert, immer `[]` |

---

## Tests

```bash
python scripts/test_geocode.py
python scripts/test_normalize_extended.py
```
