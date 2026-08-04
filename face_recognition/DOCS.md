# Face Recognition Add-on

Lokale Gesichtserkennung für Home Assistant + Frigate — läuft vollständig offline im LAN,
keine Cloud-Anbindung.

## Voraussetzungen

- Mosquitto (oder ein anderer MQTT-Broker), erreichbar aus dem Add-on
- Frigate NVR mit einer erreichbaren REST-API (`frigate_api_url`)

## Konfiguration

| Option | Beschreibung |
|---|---|
| `mqtt_host` / `mqtt_port` | MQTT-Broker, Standard `core-mosquitto:1883` |
| `mqtt_username` / `mqtt_password` | Optional, falls der Broker Auth verlangt |
| `frigate_api_url` | Basis-URL der Frigate-REST-API, z. B. `http://homeassistant.local:5000` |
| `insightface_model` | `buffalo_sc` (schnell) bis `buffalo_l` (genauer, langsamer) |
| `similarity_threshold_known` / `_unknown` | Konfidenz-Schwellwerte für Matching |
| `log_level` | Log-Verbosität |

Nach dem ersten Start lädt das Add-on das InsightFace-Modell einmalig aus dem Internet
herunter (danach läuft die Erkennung komplett offline).

## Web-UI

Über den „Open Web UI"-Button im Add-on erreichbar — kein separater Login, Zugriffsschutz
kommt über Home-Assistant-Login + LAN-Zugriff.

## Erste Schritte

1. Person anlegen, Trainingsbilder hochladen oder über „Frigate Import" aus vorhandenen
   Frigate-Erkennungen importieren
2. Training starten
3. Frigate-Events mit erkannten Personen werden automatisch verarbeitet und als
   `sensor.face_last_person` / `sensor.face_confidence` / `sensor.face_camera` in Home Assistant
   verfügbar
