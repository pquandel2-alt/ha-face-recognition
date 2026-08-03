# Frigate Import Feature — Smart Training Data from Live Events

Das **Frigate Import Feature** ermöglicht es, Trainingsbilder direkt aus Frigate-Erkennungen zu importieren — ohne manuelle Screenshots oder externe Tools.

## Workflow

### 1. Frigate Events auflisten (automatisch)

```
Frigate (läuft)
  ↓ (generiert person-events)
App "Frigate Import" Page
  ↓ (zeigt Thumbnail-Galerie)
```

Die App ruft alle Person-Events aus Frigate ab (default: letzte 50):
```bash
GET /api/frigate/snapshots?limit=50
```

Jeder Event zeigt:
- **Thumbnail** (aus Frigate)
- **Camera** (Welche Kamera)
- **Zeitpunkt** (Wann erkannt)

### 2. Snapshots auswählen

Benutzer wählt Bilder mit **Checkboxes** aus, z.B.:
- 3 Bilder von der Haustür-Kamera
- 2 Bilder von der Garage-Kamera

### 3. Person zuordnen

Linke Sidebar: **Target Person** auswählen (z.B. "Max")

### 4. Importieren

Klick "Import 5 Images" → Backend:

```python
# Für jeden selected Event:
1. Hole Snapshot-Bytes von Frigate
2. Erkenne Gesichter mit InsightFace
3. Speichere als Training-Image mit:
   - Filename (eindeutig)
   - Person-ID (Max)
   - Source = "frigate_import"
   - Frigate-Event-ID (Rückverfolgung)
   - face_detected = True/False (wurde Gesicht gefunden?)

→ Trainingsbilder sind sofort nutzbar
```

## Vorteile gegenüber manuellen Upload

| Aspekt | Manuell | Frigate Import |
|--------|---------|---|
| Workflow | Screenshot → Download → Upload | 3 Clicks |
| Bilder | Manuell geschnitten | Auto-erkannt |
| Qualität | Variabel | Frigate-Quality (optimiert) |
| Menge | 1-2 pro Versuch | 10-20 auf einmal |
| Beleuchtung | Testszenario | Echte Umgebung |
| **Zeitaufwand** | **5-10 min pro Person** | **30 sec pro Person** |

## Beispiel Use-Cases

### Szenario 1: Bekannte Person trainieren

```
Tag 1: Frigate erkennt "Max" mehrmals an Haustür
Tag 2: Öffne "Frigate Import"
       → 15 Snapshots von Max verfügbar
       → Wähle 10 beste aus
       → Import
       → Training starten (fertig!)

Ergebnis: Max ist nun trainiert von echten Haustür-Ansichten
```

### Szenario 2: Neue Person lernen

```
Gastzimmer-Kamera: Besucher kommt an
  ↓
Frigate Logs: "person detected at 18:30"
  ↓
Öffne Frigate Import:
  - Sehe Snapshot (auto-labeled)
  - Erstelle Person "Gast"
  - Import snapshot
  - Training (fertig!)

Nächstes Mal: Gast kommt → wird erkannt
```

### Szenario 3: Mehrere Kameras kombinieren

```
Haustür-Kamera: 8 Snapshots von Max
Garage-Kamera: 5 Snapshots von Max (andere Winkel)
Wohnzimmer: 6 Snapshots von Max

Import alle 19 → Training
→ Robustes Modell von Max aus allen Blickwinkeln
```

## API Endpoints

### 1. Health Check
```bash
GET /api/frigate/health
```
Response:
```json
{
  "healthy": true,
  "url": "http://192.168.1.100:5000"
}
```

### 2. Snapshots listen
```bash
GET /api/frigate/snapshots?limit=50
```
Response:
```json
{
  "events": [
    {
      "id": "abc123def456",
      "camera": "doorbell",
      "start": 1691091600,
      "end": 1691091610,
      "label": "person"
    },
    ...
  ],
  "count": 42
}
```

### 3. Snapshot importieren
```bash
POST /api/frigate/import/abc123def456
Content-Type: application/json

{
  "person_id": 1
}
```
Response:
```json
{
  "id": 42,
  "person_id": 1,
  "filename": "1_uuid_frigate_abc123def456.jpg",
  "source": "frigate_import",
  "face_detected": true,
  "faces_count": 1,
  "created_at": "2026-08-03T18:00:00"
}
```

## Implementierung Details

### Speicherung
```
/app/data/images/
├── 1_abc123_frigate_event123.jpg  (Person 1, imported from Frigate)
├── 1_def456_upload.jpg            (Person 1, manually uploaded)
├── 2_ghi789_frigate_event456.jpg  (Person 2, imported)
└── ...
```

### Datenbank
```sql
training_images
├── id: int
├── person_id: int (FK persons)
├── filename: string
├── face_detected: bool
├── source: string = 'frigate_import' | 'upload'
├── frigate_event_id: string (nullable)
└── created_at: datetime
```

Beispiel:
```sql
INSERT INTO training_images 
  (person_id, filename, face_detected, source, frigate_event_id, created_at)
VALUES
  (1, '1_uuid_frigate_abc123.jpg', TRUE, 'frigate_import', 'abc123', NOW())
```

### Face Detection beim Import
```python
# Im backend:
import cv2
from insightface import FaceAnalysis

# Snapshot-Bytes laden
snapshot_bytes = frigate.get_snapshot(event_id)

# Mit Face Engine analysieren
engine = FaceEngine()
embeddings = engine.detect_and_embed_bytes(snapshot_bytes)

# Speichern
training_image.face_detected = bool(embeddings)
training_image.has_embedding = False  # Wird beim Training berechnet
```

## Konfiguration

`.env`:
```bash
# Frigate REST API
FRIGATE_API_URL=http://192.168.1.100:5000

# Wie viele Tage zurück Events abrufen
FRIGATE_SNAPSHOT_RETENTION_HOURS=24
```

## Fehlerbehandlung

### Frigate nicht erreichbar
```
UI zeigt: "Frigate Not Available"
Fix: Prüfe FRIGATE_API_URL in .env
    curl $FRIGATE_API_URL/api/stats
```

### Keine Events verfügbar
```
UI zeigt leere Galerie
Fix: 
  - Warte auf neue Person-Events (min. 1)
  - Prüfe Frigate-Konfiguration
  - Teste Frigate UI direkt
```

### Snapshot-Import fehler
```
Error beim Import
Fix:
  - Prüfe Logs: docker compose logs api | grep import
  - Erhöhe API_TIMEOUT in config.py
  - Stelle sicher person_id existiert
```

## Performance

### Bildgröße
- Frigate Snapshot: ~150-300 KB
- App speichert original (nur Face Detection, kein Cropping)
- Pro Person: ~20 Bilder = 3-6 MB

### Request-Time
```
1. GET /api/frigate/snapshots    ~100ms
2. POST /api/frigate/import/{id} ~500ms (Snapshot laden + Face Detection)
```

## Best Practices

### 1. Diverse Bilder verwenden
```
✓ Verschiedene Kamerawinkel
✓ Unterschiedliche Tageszeiten (Tag/Nacht)
✓ Mit und ohne Brille
✓ Verschiedene Entfernungen

✗ Nur Haustür-Ansicht (nur ein Winkel)
✗ Nur Nacht-Bilder (IR, schlechtere Qualität)
```

### 2. Bilder vor Import prüfen
```
UI zeigt Thumbnail:
→ Klick auf Bild vor Import
→ Verifizieren dass Gesicht klar ist
→ Nur gute Qualität importieren
```

### 3. Regelmäßig updaten
```
Wöchentlich:
- Neue Events durchsehen
- 5-10 neue Bilder pro Person importieren
- Training neu starten
→ Mehr Robustheit gegen Beleuchtung/Winkel
```

### 4. Falsch erkannte Bilder löschen
```
Wenn Frigate "person detected" für Objekt meldet:
- Klick × auf Bild um zu unmarkieren
- Nicht importieren
→ Verhindert schlechte Trainingsdaten
```

## Automation (optional)

### Automatisches Retraining
```yaml
# Home Assistant automation
- alias: Face Recognition Auto-Retrain
  trigger:
    platform: time
    at: "02:00:00"  # Nachts
  action:
    - service: rest_command.retrain_all
      data:
        url: "http://localhost:8080/api/training/status"
```

### Snapshot Auto-Import (erweitert)
```python
# Beispiel-Script (nicht im Standard-Code)
# Könnte am Backend ergänzt werden:

# Jeden Tag neue Events auto-importieren
for event in frigate.get_recent_events(hours=24):
    # Für bekannte Personen auto-importieren
    if event.camera == 'doorbell':
        import_snapshot(event.id, person_id=1)  # Max
```

## Troubleshooting

| Problem | Ursache | Lösung |
|---------|--------|--------|
| Keine Thumbnails sichtbar | Bilder laden nicht | Prüfe FRIGATE_API_URL, Browser-Netzwerk (F12) |
| Import funktioniert aber face_detected=false | Schlechte Bildqualität/Blendung | Verwende hellere Bilder, näher zur Kamera |
| Sehr lange Import-Zeit | Netzwerk langsam | Nutze kleinere Events, höhere FRIGATE_API_URL Timeout |
| Zu viele falsch erkannte "person" Events | Frigate-Konfiguration | Erhöhe detection confidence in Frigate |

## Roadmap

Mögliche Verbesserungen:
- [ ] Batch-Import (mehrere Events gleichzeitig)
- [ ] Auto-Crop/Face-Alignment beim Import
- [ ] Thumbnail-Preview mit Face-Box
- [ ] Duplicate-Detection (ähnliche Snapshots filtern)
- [ ] Auto-Retrain Trigger nach X neuen Bildern
- [ ] Frigate Event-Annotations (Import → Auto-Label)

---

**Frigate Import = Effizienter Training mit echten Daten! 🚀**
