# Laborsuche DACH

Interaktive Karte für DEXA Body Composition Scans und Blutuntersuchungen im DACH-Raum.

**[Live-Demo →](https://huggingface.co/spaces/HenryKu/laborsuche-dach)**

## Quickstart

Voraussetzung: [Docker](https://docs.docker.com/get-docker/) und Docker Compose.

```bash
git clone https://github.com/HenryKue/laborsuche-dach.git
cd laborsuche-dach
docker compose up --build
```

Die App ist erreichbar unter:

- **http://localhost:8000** — am selben Rechner
- **http://\<lokale-IP\>:8000** — von anderen Geräten im Netzwerk (z.B. Smartphone)

Der erste Start dauert ~1–2 Minuten (Frontend-Build + Dependency-Installation). Beim Hochfahren wird die Datenbank automatisch mit den Provider-Daten befüllt.

## Architektur

```
laborsuche-dach/
├── data-retrieval/   # Scraping-Pipeline (Python)
├── backend/          # REST-API (FastAPI + PostgreSQL)
└── web-app/          # Kartenansicht (React + Leaflet)
```

**Datenfluss:**

```
Provider-URLs  →  Firecrawl (Scrape)  →  Nominatim (Geocode)  →  output/*.json
                                                                        │
                                                                  manuell kopieren
                                                                        │
                                                                        ▼
                                                              backend/data/providers.json
                                                                        │
                                                                        ▼
Browser  ←  Leaflet-Karte  ←  React-App  ←  GET /api/providers  ←  PostgreSQL
```

Die Pipeline läuft manuell und unabhängig vom Backend. Sie scrapt Anbieter-Websites und erzeugt JSON-Dateien in `data-retrieval/output/`. Diese müssen anschließend manuell nach `backend/data/providers.json` kopiert werden. Beim Start liest das Backend diese Seed-Datei und befüllt die Datenbank. Das Frontend holt die Daten über einen einzelnen API-Endpunkt und rendert sie auf der Karte.

## Daten-Pipeline

### Ansatz

Es gibt keine zentrale Datenbank oder API für DEXA- und Blutlabor-Anbieter im DACH-Raum. Die Daten sind über hunderte Einzelwebsites verstreut. Mein Ansatz kombiniert manuelle Recherche mit gezielter Automatisierung.

**1. Manuelle Recherche der Anbieter-URLs**

Für beide Kategorien (DEXA Body Composition und Blutlabor Selbstzahler) habe ich separat recherchiert und die URLs in zwei kuratierte Listen gesammelt (`data-retrieval/data/`).

**2. Automatisiertes Scraping der Kontaktdaten**

Die Zweistufen-Struktur, die Wahl von Firecrawl und Nominatim sowie das JSON-Schema habe ich selbst entworfen. Die Implementierung der Scripts habe ich mit Claude Code generiert. Ein Python-Script scrapt die gesammelten URLs mit [Firecrawl](https://www.firecrawl.dev/) und extrahiert Adressen, Telefonnummern und Websites. Bei fehlenden Angaben versucht das Script automatisch Unterseiten wie `/impressum` oder `/kontakt`.

Die Pipeline scrapt bewusst nur Kontakt- und Adressdaten. Eine automatische Klassifizierung der Dienstleistungen (z.B. "Body Composition" vs. "nur Knochendichte") wäre zu fehleranfällig.

**3. Geocoding mit Nominatim**

Ebenfalls mit Claude Code implementiert. Ein zweites Script löst die Adressen über Nominatim (OpenStreetMap) in Koordinaten auf. Ergebnisse werden gecacht, damit wiederholte Läufe keine unnötigen API-Calls erzeugen.

**4. Manuelle Verifikation und Ergänzung**

Im letzten Schritt gehe ich jeden Eintrag manuell durch und ergänze Preise, die konkreten Dienstleistungen (Body Composition vs. Knochendichte) und den Selbstzahler-Status. Die Fehlerquote bei automatischer Klassifizierung wäre für diese Felder zu hoch.

### Datenqualität

Qualität vor Quantität. Die meisten Anbieter (vor allem in Deutschland) bieten nur Knochendichtemessungen an und wurden deshalb nicht mit in die Daten aufgenommen. DEXA Body Composition und reine Knochendichtemessung werden durch manuelle Prüfung sauber getrennt. Selbstzahler-Option ist einzeln verifiziert.

Preise sind nur eingetragen wenn sie öffentlich auf der Website stehen. Ein `price_eur`-Wert von `-1` bedeutet, dass der Anbieter keine Preisinformation veröffentlicht. `null` bedeutet, dass der Preis noch nicht recherchiert wurde.

Aktuell erfasst: 23 DEXA-Anbieter, 39 Blutlabore.

## Datenmodell

Zwei Tabellen mit einer 1:n-Beziehung: Ein Provider kann mehrere Services anbieten.

**Provider** speichert Stammdaten und Standort:

| Feld                                     | Beschreibung                               |
| ---------------------------------------- | ------------------------------------------ |
| name, street, postal_code, city, country | Adresse (country als ISO 3166-1: DE/AT/CH) |
| latitude, longitude                      | Koordinaten für die Kartenansicht          |
| phone, email, website                    | Kontaktdaten (optional)                    |
| self_pay                                 | Selbstzahler möglich                       |
| source_url                               | Ursprungsseite der Daten                   |
| verified_at                              | Zeitpunkt der letzten Prüfung              |

**Service** beschreibt eine konkrete Leistung eines Providers:

| Feld        | Beschreibung                                         |
| ----------- | ---------------------------------------------------- |
| provider_id | Fremdschlüssel auf Provider                          |
| type        | `body_composition`, `bone_density` oder `blood_test` |
| price_eur   | Preis in Euro (optional)                             |

Das Modell ist bewusst normalisiert. Neue Leistungstypen lassen sich durch Erweiterung des `ServiceType`-Enums hinzufügen, ohne das Schema zu ändern. Ein Provider der sowohl DEXA als auch Bluttests anbietet hat einfach mehrere Service-Einträge.

## Kartenansicht

Die Karte zeigt alle erfassten Anbieter als farbige Marker. Rote Marker sind DEXA-Anbieter, blaue Marker sind Blutlabore. Anbieter die beides anbieten erhalten einen kombinierten Marker.

![Kartenansicht](screenshots/screenshot_1.png)

Über ein Dropdown lässt sich nach Kategorie filtern (Alle / DEXA / Blutlabor). Bei Klick auf einen Marker öffnet sich ein Seitenbereich mit Adresse, Kontaktdaten, angebotenen Leistungen und Preisen.

![Seitenbereich](screenshots/screenshot_2.png)

Bei vielen Markern auf engem Raum werden diese automatisch geclustert und erst beim Reinzoomen aufgelöst.

## Pipeline selbst ausführen

Voraussetzung: Ein [Firecrawl API-Key](https://www.firecrawl.dev/) (kostenloser Tier reicht). Umgebungsvariablen gemäß `data-retrieval/.env.example` setzen.

```bash
cd data-retrieval
pip install -r requirements.txt

# Stufe 1: Scraping
python scripts/scrape_providers.py --input data/bodycomp_provider_url.json --output output/bodycomp_providers.json
python scripts/scrape_providers.py --input data/blood_provider_url.json --output output/blood_providers.json

# Stufe 2: Geocoding
python scripts/geocode_providers.py output/bodycomp_providers.json
python scripts/geocode_providers.py output/blood_providers.json
```

Weitere Optionen und Details in `data-retrieval/README.md`.

## Entscheidungen

| Entscheidung                      | Begründung                                                                                                                                                 |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FastAPI + PostgreSQL + SQLAlchemy | Gängige Kombination in der modernen Python-Webentwicklung. Gut dokumentiert, große Community, bewährtes Zusammenspiel.                                     |
| React + Vite                      | Standard-Stack für moderne Frontends. Schneller Build, Hot Reload, TypeScript out of the box.                                                              |
| Leaflet                           | Open Source, kostenlos, keine Lizenzprobleme. Für eine Kartenanwendung mit Markern und Clustering völlig ausreichend.                                      |
| Firecrawl                         | Vereinfacht das Scraping erheblich. Rendert JavaScript, extrahiert strukturiert, und das kostenlose Kontingent reicht für dieses Projekt.                  |
| Zwei-Stufen-Pipeline              | Trennung von Scraping und Geocoding ermöglicht manuelle Validierung zwischen den Schritten. Beide Scripts laufen unabhängig und sind einzeln wiederholbar. |
| Docker Compose                    | Ein Befehl startet die gesamte Anwendung. Keine lokale Installation von PostgreSQL oder Node nötig.                                                        |

## Was ich bei mehr Zeit machen würde

- Mehr Regionen abdecken und die Datenbasis vergrößern
- Extraktionspipeline vollständig automatisieren, sodass der manuelle Validierungsschritt entfällt
- Suchfunktion nach Praxisnamen oder Orten
- Standort des Nutzers einbeziehen und die nächstgelegenen Praxen vorschlagen
- Filterung nach Land oder Umkreis
- Regelmäßiger Abgleich der Daten mit den Quellwebsites, um veraltete Einträge zu erkennen

## Technologien

| Schicht       | Stack                                      |
| ------------- | ------------------------------------------ |
| Frontend      | React 19, TypeScript, Leaflet, Bootstrap 5 |
| Backend       | FastAPI, SQLAlchemy, Pydantic              |
| Datenbank     | PostgreSQL 16                              |
| Pipeline      | Firecrawl, Geopy/Nominatim                 |
| Infrastruktur | Docker, Docker Compose                     |
