# ha-face-recognition Development Guide

Lokale Gesichtserkennungs-App für Home Assistant mit Frigate-Integration.

## Architektur-Überblick

```
Frigate (NVR)
    ↓ MQTT Event (frigate/events)
    ↓
Face Recognition Service (Backend)
    ├─ FaceEngine: InsightFace + ArcFace Embeddings
    ├─ Database: SQLAlchemy + SQLite
    ├─ MQTT: Subscribe + Publish + HA Discovery
    └─ WebSocket: Live Event Broadcasting
    ↓
Frontend (React + Vite + Tailwind)
    └─ 4 Pages: Persons, Training, Events, FrigateImport
    ↓
Home Assistant (Sensors via MQTT Discovery)
```

## Code-Organisation

- **face_recognition/backend/app/main.py**: FastAPI App, MQTT Startup, Frigate Event Handler
- **face_recognition/backend/app/services/face_engine.py**: InsightFace Wrapper + Embeddings + Matching
- **face_recognition/backend/app/services/mqtt_service.py**: paho-mqtt Client + Publishing
- **face_recognition/backend/app/routes/**: API Endpoints (persons, training, recognition, frigate)
- **face_recognition/backend/app/models/**: SQLAlchemy ORM (persons, training_images, embeddings, events)
- **face_recognition/frontend/src/pages/**: React Pages (4 Tab-Views)
- **face_recognition/frontend/src/api.js**: Axios Wrapper für Backend-Calls

## Key Concepts

### Embeddings
- 512-dim ArcFace vectors (computed from InsightFace)
- Stored as JSON in embeddings table
- Average embedding per person from all training images
- Cosine similarity used for matching (0.0-1.0)

### Thresholds
```
confidence >= 0.50  → known person
0.35 <= confidence < 0.50  → uncertain (reported as "unknown")
confidence < 0.35  → unknown
```

### Frigate Integration
- Subscribe: `frigate/events` MQTT topic
- Publish: `home/face_recognition/person` (recognition results)
- HA Discovery: Publish sensor configs to `homeassistant/sensor/...`

### Training Workflow
1. Upload images or import from Frigate
2. Click "Train" to compute average embedding
3. Embeddings stored in DB, used for live recognition

### Frigate Import Feature
- Lists recent person events from Frigate API
- User selects snapshots, assigns to person
- Backend fetches snapshot, detects faces, saves as training image
- Automatic face detection on import

## Development

### Backend Setup
```bash
cd face_recognition/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

### Frontend Setup
```bash
cd face_recognition/frontend
npm install
npm run dev  # http://localhost:3080
```

### Database
- SQLite embedded in `/data/face_db.db`
- Created on first startup via `init_db()`
- ORM via SQLAlchemy in `app/models/`

### Configuration
- `config.py`: Pydantic BaseSettings (reads from .env / HA add-on options)
- No app-level auth — protected only by HA login + LAN access, like most HA add-ons
- MQTT connection happens on app startup

## API Reference

### Persons
```
GET  /api/persons
POST /api/persons?name=John
GET  /api/persons/{id}
DEL  /api/persons/{id}
POST /api/persons/{id}/images (multipart: file)
GET  /api/persons/{id}/images
DEL  /api/persons/{id}/images/{image_id}
```

### Training
```
POST /api/training/{person_id}
GET  /api/training/status
GET  /api/training/{person_id}/status
```

### Recognition
```
POST /api/recognition/analyze (multipart: file + camera)
GET  /api/recognition/events?limit=50
```

### Frigate
```
GET  /api/frigate/health
GET  /api/frigate/snapshots?limit=50
POST /api/frigate/import/{event_id} (json: person_id)
```

### WebSocket
```
WS /api/ws/events
```
Publishes `{"type": "recognition", "person": "...", "confidence": 0.9, ...}`

## Important Files

**Backend Entry**: `face_recognition/backend/app/main.py`
- FastAPI app definition
- MQTT connection + startup
- Frigate event callback
- WebSocket handler
- HA Discovery publishing

**Face Recognition**: `face_recognition/backend/app/services/face_engine.py`
- InsightFace model loading
- Face detection + embedding
- Similarity matching
- Person embedding computation

**Frigate Service**: `face_recognition/backend/app/services/frigate_service.py`
- REST API calls to Frigate
- Snapshot + thumbnail fetching
- Event listing

**Database Models**: `face_recognition/backend/app/models/person.py`, `event.py`
- Person, TrainingImage, Embedding, RecognitionEvent
- Relationships + constraints

## Common Tasks

### Add a new endpoint
1. Create route function in `face_recognition/backend/app/routes/`
2. Add `app.include_router()` in `main.py`
3. Update frontend API wrapper in `face_recognition/frontend/src/api.js`
4. Add React component/page if UI needed

### Change face model
Edit `.env`:
```
INSIGHTFACE_MODEL=buffalo_l  # better but slower
```
Models auto-downloaded on first use.

### Adjust confidence thresholds
Edit `.env`:
```
SIMILARITY_THRESHOLD_KNOWN=0.55        # higher = stricter
SIMILARITY_THRESHOLD_UNKNOWN=0.40      # range gets narrower
```

### Debug MQTT
```bash
mosquitto_sub -h 192.168.1.100 -t "home/face_recognition/#" -v
```

### View database
```bash
sqlite3 data/face_db.db ".schema"
sqlite3 data/face_db.db "SELECT * FROM persons;"
```

## Performance Notes

- InsightFace buffalo_sc: ~200ms per image (CPU)
- buffalo_l: ~500ms per image (better accuracy)
- Database queries are indexed on person_id
- WebSocket broadcast is async (non-blocking)
- MQTT events handled in background thread

## Testing

### Manual Test: Upload & Recognition
1. Open UI at http://localhost:8080
2. Create person "Test"
3. Upload 3+ photos of same face
4. Go to Training, click Train
5. Go to Recognition, upload test image
6. Should match with high confidence

### Manual Test: Frigate Import
1. Make sure Frigate is running + has events
2. Go to "Frigate Import" page
3. Should show thumbnail gallery
4. Select snapshots, choose person, click Import
5. Check "Events" page for new recognitions

### Manual Test: MQTT
```bash
# In terminal, subscribe to events
mosquitto_sub -h 192.168.1.100 -t "home/face_recognition/person"

# Upload image via API or UI
# Should see JSON event published
```

## Troubleshooting

**Docker build fails**: Check `pip install` for missing system deps (libsm6, libxext6)
**MQTT connection timeout**: Check MQTT_HOST/PORT in .env
**Frigate import shows no events**: Check FRIGATE_API_URL, use health endpoint
**Low confidence matches**: Increase training images, use buffalo_l model, adjust threshold
**WebSocket not connecting**: Check firewall, ensure /ws/events endpoint accessible

## Future Improvements

- [ ] Parallel face detection in Frigate event handler
- [ ] Face clustering for auto-grouping similar faces
- [ ] Image preprocessing (contrast, blur detection)
- [ ] Batch training for multiple people
- [ ] Export/import person profiles
- [ ] Statistics dashboard
- [ ] Mobile app (React Native)
