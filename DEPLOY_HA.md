# Deployment auf Home Assistant Host

> **Hinweis**: Für Home Assistant OS/Supervised ist die Installation als **natives Add-on**
> über den Add-on Store der empfohlene Weg (siehe README.md, „Option A"). Diese Anleitung hier
> beschreibt den manuellen docker-compose-Weg über SSH — nützlich für Core-Installationen oder
> wenn kein Supervisor verfügbar ist.

Schritt-für-Schritt Anleitung zum Deployment auf dem HA-System.

## Voraussetzungen

- SSH-Zugriff auf HA-Host (SSH Add-on aktiviert)
- Docker + Docker Compose auf HA-Host installiert
- MQTT-Broker läuft (Mosquitto Add-on)
- Frigate läuft (als HA Add-on)

## Schritt 1: SSH Connection Setup

```bash
# Lokale SSH-Config
ssh-keygen -t rsa -b 4096 -f ~/.ssh/ha_rsa -N ""

# Public Key zu HA-Host kopieren
ssh-copy-id -i ~/.ssh/ha_rsa -p 22 root@192.168.1.100
# oder manuell in ~/.ssh/authorized_keys

# Alias hinzufügen (optional)
echo "
Host ha-host
    HostName 192.168.1.100
    User root
    IdentityFile ~/.ssh/ha_rsa
    Port 22
" >> ~/.ssh/config
```

Test:
```bash
ssh ha-host "ls /"
```

## Schritt 2: Repository klonen auf HA-Host

```bash
ssh ha-host << 'SETUP'
  cd /opt/ha-addons  # oder ein anderes Verzeichnis
  git clone https://github.com/pquandel2-alt/ha-face-recognition.git
  cd ha-face-recognition
SETUP
```

Oder manuell SSH-connected:
```bash
ssh ha-host
cd /opt
git clone https://github.com/pquandel2-alt/ha-face-recognition.git
cd ha-face-recognition
```

## Schritt 3: Konfiguration anpassen

```bash
ssh ha-host << 'CONFIG'
cd /opt/ha-face-recognition  # Adjust path

# Basis .env erstellen
cp .env.example .env

# Editieren für HA-Host
nano .env
CONFIG
```

Wichtige Werte in `.env`:
```bash
# MQTT (normalerweise localhost auf HA, oder 127.0.0.1)
MQTT_HOST=127.0.0.1
MQTT_PORT=1883

# Frigate (läuft als HA Add-on, normalerweise localhost)
FRIGATE_API_URL=http://127.0.0.1:5000

# Auth (ÄNDERN!)
AUTH_USERNAME=admin
AUTH_PASSWORD=SuperSecurePassword123!

# Face Recognition
INSIGHTFACE_MODEL=buffalo_sc

# Log Level (für Debugging)
LOG_LEVEL=INFO
```

## Schritt 4: Container starten

```bash
ssh ha-host << 'START'
cd /opt/ha-face-recognition

# Build + Start
docker compose up -d --build

# Status prüfen
docker compose ps

# Logs prüfen (ersten 50 Zeilen)
docker compose logs | head -50

# Warten bis healthy
sleep 30
docker compose logs face-recognition | tail -20
START
```

Expected Output:
```
face-recognition   Up (healthy)
```

Wenn `Exited`:
```bash
ssh ha-host "cd /opt/ha-face-recognition && docker compose logs face-recognition"
```

## Schritt 5: Zugriff über Web-UI

UI erreichbar unter:
```
http://192.168.1.100:8080
```

Login: `admin` / `SuperSecurePassword123!`

## Schritt 6: HA Integration prüfen

In Home Assistant:
1. **Settings → Devices & Services → MQTT**
2. **Integration loaded**: Prüfe dass MQTT connected ist
3. **Developer Tools → States**: Suche nach `sensor.face_`
4. Sollte sehen:
   - `sensor.face_last_person`
   - `sensor.face_confidence`
   - `sensor.face_camera`

Wenn nicht sichtbar:
```bash
# MQTT Debug auf HA-Host
ssh ha-host "docker exec mosquitto mosquitto_sub -t 'homeassistant/sensor/face_*' -v"
```

## Schritt 7: Automation erstellen (optional)

In Home Assistant `configuration.yaml`:
```yaml
automation:
  - alias: Face Recognition - Unknown Person Alert
    trigger:
      platform: mqtt
      topic: home/face_recognition/person
    condition:
      - condition: template
        value_template: '{{ trigger.payload_json.name == "unknown" }}'
    action:
      - service: notify.mobile_app_iphone
        data:
          title: "Unknown Person Detected"
          message: "{{ trigger.payload_json.camera }}: {{ trigger.payload_json.confidence | round(2) }}"
```

Oder über UI:
1. **Settings → Automations**
2. **Create Automation**
3. **Trigger**: MQTT Topic `home/face_recognition/person`
4. **Condition**: `payload_json.confidence > 0.8`
5. **Action**: Notification / Script

## Updates

Neue Version deployen:

```bash
ssh ha-host << 'UPDATE'
cd /opt/ha-face-recognition

# Pull latest
git pull origin master

# Rebuild + Restart
docker compose down
docker compose up -d --build

# Logs
docker compose logs -f
UPDATE
```

## Monitoring

### Logs streamen
```bash
ssh ha-host "cd /opt/ha-face-recognition && docker compose logs -f face-recognition"
```

### Resource-Nutzung
```bash
ssh ha-host "docker compose stats"
```

### Database-Größe
```bash
ssh ha-host "ls -lh /opt/ha-face-recognition/data/face_db.db"
```

### Alte Events löschen
```bash
ssh ha-host << 'CLEANUP'
cd /opt/ha-face-recognition

# Events älter als 30 Tage löschen
docker compose exec face-recognition sqlite3 /data/face_db.db \
  "DELETE FROM recognition_events WHERE timestamp < datetime('now', '-30 days');"

# Anzahl überbleibender Events
docker compose exec face-recognition sqlite3 /data/face_db.db \
  "SELECT COUNT(*) FROM recognition_events;"
CLEANUP
```

## Backup

Datenbank + Trainingsbilder sichern:

```bash
ssh ha-host << 'BACKUP'
cd /opt/ha-face-recognition
tar czf /tmp/face_recognition_backup_$(date +%Y%m%d).tar.gz data/
ls -lh /tmp/face_recognition_backup_*
BACKUP

# Local herunterladen
scp ha-host:/tmp/face_recognition_backup_*.tar.gz ~/backups/
```

## Restore

```bash
# .tar.gz hochladen
scp ~/backups/face_recognition_backup_20260803.tar.gz ha-host:/tmp/

# Extrahieren
ssh ha-host << 'RESTORE'
cd /opt/ha-face-recognition
rm -rf data/
tar xzf /tmp/face_recognition_backup_20260803.tar.gz
docker compose restart face-recognition
RESTORE
```

## Troubleshooting

### Container startet nicht
```bash
ssh ha-host "cd /opt/ha-face-recognition && docker compose logs face-recognition | tail -50"
```

### Port 8080/3080 bereits in Benutzung
```bash
# Anderen Service finden
ssh ha-host "netstat -tlpn | grep 8080"

# Oder andere Ports nutzen
# docker-compose.yml editieren:
# ports:
#   - "8090:8000"  # Statt 8080
```

### MQTT Connection timeout
```bash
# MQTT Broker prüfen
ssh ha-host "docker ps | grep mosquitto"

# Oder:
ssh ha-host "docker exec mosquitto mosquitto_sub -t 'test' -v" &
# (sollte warten auf Messages)
```

### Frigate API nicht erreichbar
```bash
# Frigate Container prüfen
ssh ha-host "docker ps | grep frigate"

# Test connection
ssh ha-host "curl http://127.0.0.1:5000/api/stats"

# Wenn nicht funktioniert, nutze externe IP:
# FRIGATE_API_URL=http://192.168.1.100:5000
```

## SSL/TLS (optional)

Für HTTPS Support:

```bash
# Certbot installieren
ssh ha-host "apt-get install -y certbot"

# Cert generieren
ssh ha-host "certbot certonly --standalone -d face-recognition.home.local"

# In nginx config eintragen (wenn reverse proxy genutzt)
# siehe README.md
```

## Performance-Optimierung auf HA

Wenn CPU zu hoch:

```bash
# In .env
INSIGHTFACE_MODEL=buffalo_sc  # kleiner Modell
LOG_LEVEL=WARNING             # weniger Logging
API_WORKERS=1                 # weniger Worker
```

Dann restart:
```bash
ssh ha-host "cd /opt/ha-face-recognition && docker compose restart face-recognition"
```

## Disk-Speicher

Bilder und Datenbank werden lokal gespeichert:
- `data/face_db.db` — SQLite DB (~1-10 MB)
- `data/images/` — Trainingsbilder (je nach Anzahl)
- `data/models/` — InsightFace Cache (~500 MB bei buffalo_l, ~100 MB bei buffalo_sc)

Bei Speicherplatz-Problemen:
```bash
ssh ha-host << 'CLEANUP'
cd /opt/ha-face-recognition/data

# Nur älteste Bilder behalten
find images -type f -mtime +180 -delete

# Größe prüfen
du -sh .
CLEANUP
```

## Production Checkliste

- [x] .env mit sicheren Credentials
- [x] MQTT_HOST / FRIGATE_API_URL korrekt
- [x] Docker Logs auf ERROR prüfen
- [x] Test: Web-UI lädt
- [x] Test: Person erstellen + trainieren
- [x] Test: MQTT Events publishen
- [x] Test: HA Sensoren sichtbar
- [x] Backup vor erstem großen Deploy
- [x] Monitoring einrichten (Logs, Disk, CPU)
- [x] Automation in HA erstellen

## Support

Fehler? Check:
1. `docker compose logs face-recognition` — Backend/Frontend-Fehler (ein Container für beides)
2. Browser-Console (F12) — JavaScript Fehler
3. HA Logs — MQTT Connection
4. Logs im `DEPLOY_HA.md` im Repo
