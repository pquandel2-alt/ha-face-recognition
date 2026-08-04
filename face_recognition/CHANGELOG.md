# Changelog

## 1.0.6

- Fix: Frontend bekam nach dem Ändern der `auth_username`/`auth_password`-Add-on-Optionen
  (weg von den Defaults `admin`/`changeme`) nur noch `401 Unauthorized` auf jeden API-Call
  (`/api/persons`, `/api/frigate/health`, insbesondere sichtbar auf der „Frigate Import"-Seite).
  Ursache: `frontend/src/api.js` liest die Basic-Auth-Credentials aus `localStorage`, fiel dort
  aber mangels UI ohne gespeicherte Werte fest auf die hartcodierten Defaults `admin`/`changeme`
  zurück — es gab schlicht **keine Möglichkeit**, im Frontend andere Zugangsdaten einzugeben.
  Die App funktionierte also nur solange, wie die Add-on-Auth-Optionen exakt auf den
  Werkseinstellungen standen.
  Fix: neue `LoginGate`-Komponente (`frontend/src/components/LoginGate.jsx`) fragt beim ersten
  Aufruf Benutzername/Passwort ab, verifiziert sie gegen `/api/persons` und speichert sie erst
  bei Erfolg in `localStorage`; bei falschen Zugangsdaten wird eine Fehlermeldung angezeigt statt
  stillschweigend mit ungültigen Defaults weiterzumachen. Zusätzlich ein „Abmelden"-Button im
  Header, um gespeicherte Zugangsdaten zurückzusetzen. `api.js` verwendet keine hartcodierten
  Fallback-Credentials mehr.

## 1.0.5

- Fix: Fehlende/falsche Basic-Auth-Header führten zu `500 Internal Server Error` statt zum
  korrekten `401 Unauthorized`. Ursache: `BasicAuthMiddleware` warf `raise HTTPException(...)`
  direkt aus `dispatch()`. Bei `BaseHTTPMiddleware` liegt dieser Code aber außerhalb der
  FastAPI-Exception-Handling-Schicht — die Exception landet unbehandelt bei Starlettes
  `ServerErrorMiddleware` und wird zu einem generischen 500. Fix: die Middleware gibt bei
  fehlender/falscher Auth jetzt direkt eine `JSONResponse(401)` zurück statt zu `raise`n.
  Betraf alle `/api/*`-Aufrufe ohne (oder mit falschem) Basic-Auth-Header.

## 1.0.4

- Fix: `AttributeError: module 'paho.mqtt.client' has no attribute 'CallbackAPIVersion'` beim
  Start. `mqtt_service.py` ist komplett auf die paho-mqtt-2.x-API geschrieben
  (`mqtt.CallbackAPIVersion.VERSION2`, `on_connect`/`on_disconnect` mit `reason_code`/
  `properties`), `requirements.txt` pinnte aber noch die alte `1.6.1` (dort existiert die
  Callback-API-Versionierung schlicht nicht). Auf `2.1.0` angehoben. Geprüft: es gibt im
  Code nur diese eine Stelle, die paho-mqtt nutzt — keine weiteren Versions-Konflikte.

## 1.0.3

- Fix: `onnxruntime` fehlte komplett in `requirements.txt`. `insightface` benötigt es zur Laufzeit
  als eigentliche Inference-Engine (`onnx` ist nur das Modellformat), deklariert es aber selbst
  nicht als Abhängigkeit in seinen PyPI-Metadaten — daher installierte `pip install insightface`
  es nie automatisch mit. Auf `1.18.1` gepinnt (kompatibel mit dem gepinnten `numpy==1.24.4`).
- Zusätzlich: alle Backend-Imports einmal vollständig gegen `requirements.txt` geprüft
  (`grep` über `app/`) — keine weiteren Lücken gefunden.

## 1.0.2

- Fix: `opencv-python` (GUI-Variante) durch `opencv-python-headless` ersetzt — die volle
  Variante zog immer neue X11/GTK-Laufzeitbibliotheken nach (erst `libGL.so.1`, dann
  `libgthread-2.0.so.0`, potenziell weitere). Headless ist für Server/Container gemacht und
  braucht keine davon. Dockerfile entsprechend bereinigt (nur noch `build-essential` +
  `libgomp1` nötig).

## 1.0.1

- Fix: `opencv-python==4.10.1.26` existierte nicht auf PyPI — auf `4.10.0.84` korrigiert
- Fix: `build-essential` ergänzt (insightface kompiliert eine C++/Cython-Extension, g++ fehlte)
- Fix: `libgl1` ergänzt (cv2 benötigt `libGL.so.1` zur Laufzeit, sonst Absturz beim Start)

## 1.0.0

- Erste Version als natives Home Assistant Add-on
- Konsolidierung von Backend + Frontend in einen Container
- Konfiguration über die native Add-on-Options-UI
