# Testing Guide

Schnelle Tests für ha-face-recognition nach Installation.

## Schritt 1: Container-Status prüfen

```bash
docker compose ps
```

Expected:
```
NAME                    STATUS
face-recognition-api       Up (healthy)
face-recognition-frontend  Up (healthy)
```

Logs prüfen:
```bash
docker compose logs api     # Backend logs
docker compose logs frontend # Frontend logs
```

## Schritt 2: API Health Check

```bash
curl -u admin:changeme http://localhost:8080/health
```

Expected:
```json
{
  "status": "ok",
  "mqtt_connected": true
}
```

Wenn `mqtt_connected: false`:
- Prüfe MQTT_HOST in .env
- Prüfe dass MQTT-Broker läuft
- Logs: `docker compose logs api | grep MQTT`

## Schritt 3: Web-UI laden

Öffne: http://localhost:3080

Login: `admin` / `changeme`

Sollte **4 Navigation-Links** oben sehen:
- Persons ✓
- Training ✓
- Events ✓
- Frigate Import ✓

## Schritt 4: Person erstellen & trainieren

### 4a. Person hinzufügen
1. Gehe zu **Persons**
2. Eingabe: `Test Person`
3. Klick "Add Person"

Expected: Card erscheint mit "0 images"

### 4b. Bilder hochladen
1. Klick auf die Card um auszuklappen
2. Klick auf "Click to upload" Area
3. Wähle 3-5 Bilder von der gleichen Person aus
4. Upload sollte nach kurzer Zeit abgeschlossen sein

Expected: Images erscheinen in Grid

### 4c. Training starten
1. Gehe zu **Training**
2. Klick "Train" für "Test Person"
3. Status sollte auf "✓ Trained" wechseln

Expected: "Faces detected: N"

Wenn Fehler `No faces detected`:
- Bilder müssen Gesichter enthalten (Größe mind. 50x50px)
- Versuche mit besserer Beleuchtung
- Nutze Portrait-Modus (vertikal)

## Schritt 5: Gesichtserkennung testen

### 5a. Test-Bild analyse
1. Gehe zu **Recognition**
2. Upload ein Bild von "Test Person"
3. Sollte sofort analysieren und Ergebnis zeigen

Expected: `Test Person` mit Confidence > 0.8

### 5b. Events anschauen
1. Gehe zu **Events**
2. Sollte die Uploads und Erkennungen sehen

Expected: Live-Events in Timeline

## Schritt 6: Frigate-Integration testen (optional)

```bash
# Prüfe Frigate Erreichbarkeit
curl http://192.168.1.100:5000/api/stats
```

Wenn erfolgreich:

1. Gehe zu **Frigate Import**
2. Sollte Thumbnail-Galerie zeigen

Expected: Snapshots vom Frigate erscheinen

Wenn "Frigate Not Available":
- Prüfe FRIGATE_API_URL in .env
- Prüfe dass Frigate läuft
- Test: `curl $FRIGATE_API_URL/api/stats`

## Schritt 7: MQTT Integration testen

Terminal 1 — MQTT abonnieren:
```bash
mosquitto_sub -h 192.168.1.100 -t "home/face_recognition/#" -v
```

Terminal 2 — Test-Event publishen (simuliert Frigate):
```bash
mosquitto_pub -h 192.168.1.100 -t "homeassistant/sensor/face_last_person/state" \
  -m '{"name": "Test Person", "confidence": 0.92, "camera": "test", "time": "2026-08-03T18:00:00"}'
```

Expected in Terminal 1:
```
homeassistant/sensor/face_last_person/state Test Person
```

## Schritt 8: Home Assistant Sensoren prüfen

In Home Assistant:
1. Gehe zu **Developer Tools → States**
2. Suche nach `sensor.face_`

Sollte sehen:
- `sensor.face_last_person`
- `sensor.face_confidence`
- `sensor.face_camera`

Wenn nicht sichtbar:
- Warte 30s bis Discovery processed ist
- Prüfe Home Assistant Logs
- Refresh Browser

## Database-Zustand prüfen

```bash
# Shell in Container
docker compose exec api sh

# SQLite prüfen
sqlite3 /app/data/face_db.db

# SQL-Queries
> SELECT * FROM persons;
> SELECT COUNT(*) FROM training_images;
> SELECT COUNT(*) FROM embeddings;
> SELECT * FROM recognition_events LIMIT 5;
```

## Performance-Check

### Response-Times
```bash
# API Response Zeit
time curl -u admin:changeme http://localhost:8080/api/persons

# Sollte < 100ms sein
```

### Log-Analyse
```bash
# Backend logs nach Fehler
docker compose logs api | grep -i error

# MQTT debug
docker compose logs api | grep -i mqtt
```

## Cleanup nach Tests

```bash
# Alle Personen löschen (neue Runde)
docker compose exec api sqlite3 /app/data/face_db.db \
  "DELETE FROM persons; DELETE FROM training_images; DELETE FROM recognition_events;"

# Bilder löschen
rm -f data/images/*
```

## Troubleshooting Checkliste

| Issue | Fix |
|-------|-----|
| 401 Unauthorized | Prüfe Auth Header, `curl -u admin:changeme` |
| MQTT not connected | Prüfe MQTT_HOST/.PORT in .env |
| Frigate import zeigt nichts | Prüfe FRIGATE_API_URL, test `curl $URL/api/stats` |
| Keine Gesichter erkannt | Bilder müssen klar sein, mind. 50x50px Gesicht |
| WebSocket connection failed | Prüfe Browser-Konsole (F12), Firewall |
| Langsame Recognition | Nutze `buffalo_sc` statt `buffalo_l` |
| Disk voll | `docker system prune`, `rm data/images/*` |

## Performance Tipps

### Schnelleres Deployment
```bash
# Nutze buffalo_sc Model (default, schneller)
# Verhindere häufige Rebuilds
docker compose up -d  # ohne --build wenn nicht nötig
```

### Schnellere Recognition
```bash
# In .env
INSIGHTFACE_MODEL=buffalo_sc  # 200ms statt 500ms
SIMILARITY_THRESHOLD_KNOWN=0.55  # Schneller matchen (strikte)
```

### Speicheroptimierung
```bash
# Alte Events löschen (älter als 30 Tage)
docker compose exec api sqlite3 /app/data/face_db.db \
  "DELETE FROM recognition_events WHERE timestamp < datetime('now', '-30 days');"

# Images Cleanup
find data/images -mtime +30 -delete
```

## End-to-End Test (5 min)

```bash
#!/bin/bash
# Kompletter Test-Flow

echo "1. Health Check..."
curl -s -u admin:changeme http://localhost:8080/health | jq .

echo "2. Create Person..."
PERSON_ID=$(curl -s -u admin:changeme -X POST "http://localhost:8080/api/persons?name=E2ETest" | jq .id)
echo "Created: $PERSON_ID"

echo "3. Upload 3 test images..."
for i in 1 2 3; do
  # Benötigt echte Bilddateien in ./test_images/
  curl -u admin:changeme -F "file=@test_images/person$i.jpg" \
    http://localhost:8080/api/persons/$PERSON_ID/images
done

echo "4. Train..."
curl -u admin:changeme -X POST http://localhost:8080/api/training/$PERSON_ID | jq .

echo "5. Recognize test image..."
curl -u admin:changeme -F "file=@test_images/test.jpg" -F "camera=test" \
  http://localhost:8080/api/recognition/analyze | jq .

echo "✓ E2E Test Complete!"
```

## Logs exportieren für Bug Reports

```bash
docker compose logs > logs.txt
docker compose logs api > backend.log
docker compose logs frontend > frontend.log
```
