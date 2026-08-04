# Changelog

## 1.0.11

- Neu (auf Nutzerwunsch: Vergleich der eigenen Erkennung mit Frigates eingebauter
  Gesichtserkennung, um Frigates wiederholte Fehlerkennungen einordnen zu können):
  Jedes Recognition-Event zeigt jetzt zusätzlich Frigates eigenen `sub_label`-Treffer samt
  Konfidenz (`data.sub_label_score`) direkt neben dem Ergebnis dieser App an. Weichen beide
  Ergebnisse voneinander ab, wird die Event-Zeile in der Events-Ansicht farblich hervorgehoben.
  Technisch: Frigates eigene Erkennung ist beim `"new"`-Event (dem bisher einzig verarbeiteten
  Event-Typ) noch nicht fertig — daher wird jetzt zusätzlich auf den `"end"`-Event reagiert,
  das zugehörige Frigate-Event per REST nachgeladen und das bereits gespeicherte Recognition-Event
  nachträglich mit `frigate_sub_label`/`frigate_sub_label_score` ergänzt (neue, migrierte
  DB-Spalten — bestehende `face_db.db`-Dateien werden beim Start automatisch erweitert).
- Fix: Die WebSocket-Live-Aktualisierung der Events-Seite sendete den Personennamen unter dem
  Feld `person`, das Frontend las aber `person_name` — live per WebSocket eintreffende Events
  zeigten dadurch keinen Namen an. Zusätzlich überschrieb die alte Live-Liste dauerhaft die
  per REST abgefragte Liste, sobald ein einziges WebSocket-Event eingetroffen war — nachträglich
  ergänzte Daten (wie Frigates `sub_label`, der erst mit Verzögerung eintrifft) wurden für bereits
  angezeigte Zeilen nie sichtbar. Die Events-Seite nutzt WebSocket-Nachrichten jetzt nur noch als
  Signal, die REST-Liste neu zu laden, die weiterhin alleinige Datenquelle bleibt.

## 1.0.10

- Fix (Log-Analyse nach Nutzer-Fehlermeldung: „Nach dem 4. Training kommen Fehlermeldungen"):
  `POST /api/training/{person_id}` schlug für Personen mit wenigen importierten Frigate-Bildern
  mit `400: Failed to compute embedding (no faces detected)` fehl (konkret: Andy, 2 importierte
  Bilder, 0 davon als Gesicht erkannt). Ursache: `compute_person_embedding()` lässt InsightFace
  beim Training auf jedem Trainingsbild erneut eine eigene Gesichtserkennung laufen — auch auf
  Frigates eigenen, bereits eng zugeschnittenen trainierten Gesichts-Crops (aus dem in 1.0.9
  hinzugefügten Import-Feature). Diese Crops füllen fast den kompletten Bildrahmen ohne Rand;
  InsightFace' RetinaFace-Detektor ist aber auf normale Fotos mit Kontext um das Gesicht trainiert
  und scheitert bei randlosen Ausschnitten häufig komplett. Das betraf nicht nur Andy sichtbar:
  bei Philipp z.B. wurden nur 13 von 32 importierten Bildern erkannt — bei genug Puffer fiel das
  nur nicht als harter Fehler auf, bei Andy mit nur 2 Bildern (0 Treffer) schon.
  Fix: `face_engine.py` versucht bei einem leeren Erkennungs-Ergebnis jetzt automatisch einen
  zweiten Durchlauf auf einer gepolsterten Kopie des Bildes (Rand von 50 % der Bildgröße,
  `cv2.copyMakeBorder` mit `BORDER_REPLICATE`) — gibt dem Detektor den fehlenden Kontext-Rand
  zurück, ohne normale Fotos zu beeinflussen (dort wird der erste Durchlauf ohnehin fündig).
  Betroffene Personen (v.a. Andy) sollten das Training nach dem Update erneut anstoßen; bereits
  erfolgreich trainierte Personen können optional neu trainiert werden, um zusätzliche, vorher
  übersprungene Bilder mit einzubeziehen.

## 1.0.9

- Fix: „Frigate Import" zeigte nach dem Routing-Fix in 1.0.7 zwar Bilder an, aber die falschen —
  generische Frigate-Bewegungserkennungs-Snapshots (`label=person`-Events) statt der Gesichter,
  mit denen Frigates eigene Face-Recognition-Funktion bereits trainiert wurde. Frigate führt
  intern eine komplett getrennte, bereits nach Personennamen sortierte Galerie manuell trainierter
  Gesichtsbilder (`GET /api/faces` → `{Name: [Dateinamen], ...}`, Bilder unter
  `/clips/faces/{Name}/{Datei}`) — genau das wollte der Nutzer importieren können, nicht die
  rohen Bewegungs-Thumbnails.
  Neu: Tab „Trainierte Gesichter (aus Frigate)" auf der Import-Seite (jetzt Standard-Tab) zeigt
  je Frigate-Personenname eine Bildergalerie, mit Mehrfachauswahl, Zuordnung zu einer bestehenden
  oder neu anzulegenden Person, und Batch-Import als Trainingsbilder. Der bisherige generische
  Ereignis-Import bleibt als zweiter Tab „Personen-Ereignisse" erhalten (weiterhin nützlich für
  Personen, die Frigate noch nicht selbst gelernt hat).
  Backend: `frigate_service.py` um `get_trained_faces()` (holt `/api/faces`, entfernt den
  `train`-Schlüssel — das ist Frigates automatische, unbestätigte Erkennungs-Sammlung, keine
  manuell trainierten Bilder) und `get_face_image(name, filename)` ergänzt. Neue Routen
  `GET /api/frigate/faces` (Liste), `GET /api/frigate/faces/{name}/{filename}` (Bild-Proxy,
  mit Pfad-Traversal-Schutz) und `POST /api/frigate/faces/import` (Batch-Import inkl.
  Gesichtserkennung auf den importierten Bildern) in `routes/frigate.py`.
  Frontend: `AuthImage`-Komponente verallgemeinert (vorher `FrigateThumbnail`, jetzt beliebige
  Proxy-URL statt nur Event-Thumbnails) und für beide Tabs wiederverwendet.

## 1.0.8

- Entfernt: die app-interne Basic-Auth-Anmeldung (Backend-Middleware, `LoginGate`-Login-Formular,
  `auth_username`/`auth_password`/`auth_enabled`-Optionen) ist komplett raus, auf Nutzerwunsch.
  Die App läuft ohnehin nur im LAN, geschützt durch den Zugriffsschutz von Home Assistant selbst —
  ein zusätzliches App-Login war unnötige Reibung ohne echten Sicherheitsgewinn, wie bei den
  meisten HA-Add-ons üblich (kein Ingress-Login o.ä.). `/api/*` ist jetzt offen erreichbar wie
  Frontend-Assets und `/health` es vorher schon waren.
  Betroffen: `backend/app/main.py` (BasicAuthMiddleware entfernt), `backend/app/config.py`
  (auth_* Settings entfernt), `config.yaml` (Options + Schema bereinigt), `frontend/src/api.js`
  (kein Basic-Auth-Header mehr), `frontend/src/components/LoginGate.jsx` gelöscht,
  `frontend/src/App.jsx` (kein Login-Gate, kein Abmelden-Button mehr).

## 1.0.7

- Fix (echter Root-Cause hinter „Login funktioniert nicht" + „Frigate Import kaputt"):
  `routes/persons.py` registrierte die Liste/Anlage-Route als `APIRouter(prefix="/persons")` +
  `@router.get("/")`/`@router.post("/")` — der tatsächliche Pfad war damit `/api/persons/`
  (mit Slash am Ende). Das Frontend ruft aber überall `/api/persons` (ohne Slash) auf. Starlette
  matcht Routen in Registrierungsreihenfolge und wertet dabei nur exakte Treffer; die
  Catch-all-SPA-Route (`@app.get("/{full_path:path}")`, ganz am Ende registriert, für React-Router
  Deep-Links) griff hier zuerst mit vollem Match und lieferte für alles unter `api/` explizit
  `404 Not Found` — nie eine Weiterleitung, nie die echte Personen-Liste. Dieser Bug war die
  ganze Zeit da, wurde aber vom parallelen 401-Auth-Bug maskiert: solange Requests schon an der
  Basic-Auth-Middleware scheiterten, kamen sie nie bis zum Routing durch. Erst mit v1.0.6 (Login
  funktionierte jetzt) wurde der 404 sichtbar.
  Direkte Folgen dieses einen Bugs:
  - Die neue `LoginGate`-Komponente aus 1.0.6 prüft Zugangsdaten über genau diesen Aufruf
    (`GET /api/persons`) — jeder Login schlug fehl (404 statt 200), unabhängig davon ob
    Benutzername/Passwort korrekt waren. Daher „das Anmeldeformular hat noch nie funktioniert".
  - Die „Frigate Import"-Seite lädt die Personen-Liste für die Zielperson-Auswahl über denselben
    Aufruf — die Sidebar war deshalb immer leer, Import unmöglich.
  Fix: Routen auf `@router.get("")`/`@router.post("")` geändert → tatsächlicher Pfad jetzt exakt
  `/api/persons`, matcht direkt ohne Umweg über die Catch-all-Route.
- Fix: `LoginGate.jsx` behandelte jeden Fehlschlag beim Verifizieren (egal ob 401, 404, 500 oder
  Netzwerkfehler) pauschal als „Benutzername oder Passwort falsch" und löschte die eingegebenen
  Zugangsdaten. Jetzt wird nur noch ein echtes `401` als falsches Passwort gewertet; andere
  Server-Fehler bzw. „Server nicht erreichbar" werden als solche angezeigt statt fälschlich dem
  Passwort angelastet.
- Fix: Snapshot-Thumbnails auf der „Frigate Import"-Seite luden nie, unabhängig vom obigen Bug.
  Ursache 1: `process.env.VITE_FRIGATE_API` ist im Vite-Browser-Bundle immer `undefined` (Vite
  exponiert Env-Variablen als `import.meta.env.VITE_*`, nicht über Node's `process.env` — das war
  im Frontend-Code schlicht nie erreichbar), es griff also immer der Fallback
  `http://localhost:5000`. Ursache 2: selbst korrekt aufgelöst wäre das der falsche Host (der
  Browser des Nutzers, nicht der HA-Host) UND Frigates REST-Port `5000` ist im Frigate-Add-on gar
  nicht auf das LAN exposed (nur intern im HA-Docker-Netz erreichbar) — direkte
  Browser-zu-Frigate-Requests können hier grundsätzlich nie funktionieren.
  Fix: neue Backend-Proxy-Endpunkte `GET /api/frigate/thumbnail/{event_id}` und
  `GET /api/frigate/snapshot/{event_id}` (nutzen den bereits vorhandenen, aber bis dato von keiner
  Route genutzten `frigate_service.get_thumbnail()`/`get_snapshot()`). Da `/api/*` Basic-Auth
  verlangt und ein normales `<img src=...>` keine Custom-Header mitschicken kann, lädt das
  Frontend die Thumbnails jetzt über eine neue `FrigateThumbnail`-Komponente per authentifiziertem
  `axios`-Request als Blob und zeigt sie über eine Object-URL an.

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
