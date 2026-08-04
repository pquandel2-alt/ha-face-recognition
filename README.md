# Face Recognition Service for Home Assistant

Lokale Gesichtserkennungs-App für Home Assistant mit Frigate NVR Integration. Kein Cloud-Zugriff, vollständig selbst gehostet.

## Features

- 🎯 **Gesichtserkennung**: InsightFace mit ArcFace Embeddings
- 📸 **Frigate Integration**: Automatische Snapshot-Analyse via MQTT
- 🏠 **Home Assistant**: Automatische Sensoren-Erstellung via MQTT Discovery
- 👥 **Personenmanagement**: Training, Bilder-Upload, Verwaltungs-UI
- 🎓 **Smart Training**: Import von Frigate-Snapshots als Trainingsbilder
- 🌐 **Moderne Web-UI**: React + Tailwind CSS
- 🐳 **Docker Ready**: docker-compose für einfaches Deployment

## Voraussetzungen

### Hardware
- CPU: Intel Core i5 oder besser (CPU-only, kein GPU nötig)
- RAM: 4 GB minimum (8 GB empfohlen)
- Disk: 2 GB für Models + Daten
- Linux/Docker Host

### Software
- Docker & Docker Compose
- MQTT Broker (z.B. auf HA-Host unter `192.168.1.100:1883`)
- Frigate NVR (läuft als HA Add-on)

## Installation

### Option A: Als Home Assistant Add-on (empfohlen für HAOS/Supervised)

1. **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
2. URL eintragen: `https://github.com/pquandel2-alt/ha-face-recognition`
3. Add-on **„Face Recognition"** in der Liste öffnen → **Install**
4. Im **„Configuration"**-Tab die Options ausfüllen (MQTT, Frigate-URL, Zugangsdaten — siehe
   [face_recognition/DOCS.md](face_recognition/DOCS.md))
5. **Start** → nach dem ersten Boot (Modell-Download, ca. 1-2 Minuten) über den
   **„Open Web UI"**-Button erreichbar

Falls der Store-Import mit „is not a valid app repository" fehlschlägt: den Repository-Eintrag
entfernen und erneut hinzufügen (Supervisor cached fehlgeschlagene Versuche teils zwischen).

### Option B: Docker Compose (manuell, z. B. via SSH auf den HA-Host)

#### 1. Repository klonen
```bash
git clone https://github.com/pquandel2-alt/ha-face-recognition.git
cd ha-face-recognition
```

#### 2. Konfiguration
```bash
cp .env.example .env
```

Dann `.env` anpassen:
```bash
# MQTT
MQTT_HOST=192.168.1.100
MQTT_PORT=1883

# Frigate
FRIGATE_API_URL=http://192.168.1.100:5000

# Auth
AUTH_USERNAME=admin
AUTH_PASSWORD=dein-sicheres-passwort

# Face Recognition
INSIGHTFACE_MODEL=buffalo_sc  # oder buffalo_l für bessere Genauigkeit
SIMILARITY_THRESHOLD_KNOWN=0.50
SIMILARITY_THRESHOLD_UNKNOWN=0.35
```

#### 3. Starten
```bash
docker compose up -d --build
```

Die erste Build dauert ~5-10 Minuten (InsightFace-Modell wird heruntergeladen).

## Zugriff

- **Web-UI**: http://localhost:8080
- **API**: http://localhost:8080/api
- **API Docs**: http://localhost:8080/docs

Default Auth: `admin` / `changeme` (bitte in .env ändern!)

## Workflow

### 1. Personen anlegen
1. Gehe zu "Persons"
2. Gib Namen ein und klick "Add Person"

### 2. Trainingsbilder hinzufügen
Zwei Optionen:

**Option A: Manuell hochladen**
1. Klick auf die Person um auszuklappen
2. Drag-and-drop oder click zum Upload von Bildern
3. Idealerweise 5-10 Bilder mit verschiedenen Blickwinkeln

**Option B: Frigate Import (neu!)**
1. Gehe zu "Frigate Import"
2. Wähle die Person aus (linke Sidebar)
3. Wähle Snapshots aus der Frigate-Galerie
4. Klick "Import" um sie automatisch als Trainingsbilder zu speichern
5. Die Bilder werden analysiert und die erkannten Gesichter gespeichert

### 3. Training durchführen
1. Gehe zu "Training"
2. Klick "Train" für die Person
3. Embeddings werden aus allen Trainingsbildern berechnet
4. Status ändert sich zu "✓ Trained"

### 4. Echtzeit-Events beobachten
1. Gehe zu "Events"
2. Warte auf Frigate-Erkennungen oder lade test-Bilder hoch
3. Erkannte Personen erscheinen live in der Liste

## Home Assistant Integration

Nach dem Start publiziert die App automatisch HA MQTT Discovery Configs.
In Home Assistant sollten automatisch folgende Sensoren erscheinen:

- `sensor.face_last_person` — zuletzt erkannte Person
- `sensor.face_confidence` — Konfidenz der Erkennung (%)
- `sensor.face_camera` — Kamera, auf der erkannt wurde

### Automationen erstellen
```yaml
automation:
  - alias: Face Recognition Alert
    trigger:
      platform: mqtt
      topic: home/face_recognition/person
    condition:
      - condition: template
        value_template: '{{ trigger.payload_json.confidence > 0.8 }}'
    action:
      - service: notify.mobile_app_iphone
        data:
          message: '{{ trigger.payload_json.name }} detected on {{ trigger.payload_json.camera }}'
```

## API Endpoints

### Personen
- `GET /api/persons` — Liste aller Personen
- `POST /api/persons?name=Max` — Neue Person anlegen
- `DELETE /api/persons/{id}` — Person löschen
- `POST /api/persons/{id}/images` — Bild hochladen
- `GET /api/persons/{id}/images` — Bilder einer Person
- `DELETE /api/persons/{id}/images/{image_id}` — Bild löschen

### Training
- `POST /api/training/{person_id}` — Training starten
- `GET /api/training/status` — Status aller Personen

### Erkennung
- `POST /api/recognition/analyze` — Bild analysieren (Form: `file` + `camera`)
- `GET /api/recognition/events` — Letzte Events

### Frigate
- `GET /api/frigate/health` — Frigate-Status
- `GET /api/frigate/snapshots` — Verfügbare Snapshots
- `POST /api/frigate/import/{event_id}` — Snapshot importieren (JSON: `{"person_id": 1}`)

### WebSocket
- `WS /api/ws/events` — Live-Events streamen

## Konfiguration

### Modelle
```bash
# CPU-optimiert (empfohlen für schwache Hardware)
INSIGHTFACE_MODEL=buffalo_sc    # ~60 MB

# Bessere Genauigkeit (mehr Ressourcen)
INSIGHTFACE_MODEL=buffalo_l     # ~300 MB
```

### Confidence Thresholds
```bash
# Matching-Schwellwerte (0.0 - 1.0)
SIMILARITY_THRESHOLD_KNOWN=0.50     # >= 0.50 = erkannte Person
SIMILARITY_THRESHOLD_UNKNOWN=0.35   # 0.35-0.50 = unsicher (wird als "unknown" gemeldet)
# < 0.35 = unbekannte Person
```

## Troubleshooting

### "MQTT connection failed"
- Prüfe MQTT_HOST und MQTT_PORT in .env
- Prüfe, dass MQTT-Broker läuft: `mosquitto -c config.conf`
- Teste mit: `mosquitto_sub -h 192.168.1.100 -t "frigate/#" -v`

### "Frigate health check failed"
- Prüfe FRIGATE_API_URL in .env
- Teste Frigate direkt: `curl http://192.168.1.100:5000/api/stats`
- Frigate muss auf Port 5000 erreichbar sein

### "No faces detected in training images"
- Bilder müssen Gesichter enthalten (min. ~50x50 Pixel)
- Versuch mit besserer Beleuchtung
- Hochformat (Portrait) funktioniert besser als Landschaft
- Min. 3-5 Bilder pro Person

### "Low confidence matches"
- Trainiere mit mehr Bildern (5-10 pro Person)
- Verwende unterschiedliche Blickwinkel und Beleuchtung
- Erhöhe `SIMILARITY_THRESHOLD_KNOWN` wenn zu viele False-Positives
- Oder nutze `buffalo_l` Modell für bessere Genauigkeit

### Docker Logs
```bash
docker compose logs -f face-recognition
```

## Production-Deployment auf HA

### Auf HA-Host:
```bash
# SSH in HA-Host
ssh ha-host

# Repository klonen
git clone https://github.com/pquandel2-alt/ha-face-recognition.git
cd ha-face-recognition

# Konfigurieren
cp .env.example .env
# .env anpassen (Credentials!)

# Starten
docker compose up -d --build

# Logs prüfen
docker compose logs -f
```

Die App läuft jetzt unter:
- UI: http://ha-host:8080
- API: http://ha-host:8080/api

### Nginx Reverse-Proxy (optional)
```nginx
server {
    listen 80;
    server_name face-recognition.home.local;

    location / {
        proxy_pass http://127.0.0.1:3080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8080/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Performance-Tipps

### CPU-Auslastung reduzieren
- Nutze `buffalo_sc` Model (default)
- Reduziere Frigate-Event-Rate in Config
- Nutze SIMILARITY_THRESHOLD zur schnellen Filterung

### RAM sparen
- Weniger als 10 Personen × 20 Bilder sind optimal
- Die InsightFace-Modelle cached lokal (~200-500 MB)

### Snapshot-Rotation
```bash
# Alte Snapshots nach X Tagen löschen
find /data/images -type f -mtime +30 -delete
```

## Entwicklung

Backend in Python:
```bash
cd face_recognition/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Frontend in Node:
```bash
cd face_recognition/frontend
npm install
npm run dev    # auf http://localhost:3080
npm run build  # Produktion
```

## Lizenz

MIT

## Support

Fehler? Issues auf GitHub oder README.md erweitern!
