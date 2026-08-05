# Changelog

## 1.0.18

- Feature (schnellere Echtzeit-Erkennung während der Anwesenheit): Die in v1.0.17 eingeführte
  Update-Poll-Logik (Erkennung schon während die Person noch vor der Kamera steht, nicht erst
  beim Verlassen) läuft jetzt deutlich schneller pro Zyklus, ohne die Zuverlässigkeits-Logik
  (Multi-Crop-Konsens, Sicherheitsabstand) zu verändern:
  - `FrigateService` nutzt jetzt eine wiederverwendete `requests.Session()` statt für jeden
    Aufruf eine neue Verbindung zum Frigate-Host aufzubauen.
  - `get_train_face_crops` holt die mehreren Gesichts-Crops eines Events jetzt parallel statt
    nacheinander.
  - `_analyze_crops_for_consensus` analysiert diese Crops ebenfalls parallel (jeder Worker mit
    eigener kurzlebiger DB-Session, da SQLAlchemy-Sessions nicht zwischen Threads geteilt werden
    dürfen).
  - Das Poll-Intervall während einer aktiven Anwesenheit
    (`frigate_update_check_interval_seconds`) wurde von 2s auf 1s gesenkt, da die Pipeline durch
    die obigen Änderungen genug Luft dafür hat.

## 1.0.17

- Feature (Einzel-Embeddings + k-NN-Matching statt Mittelwert pro Person): Jedes
  Trainingsbild bekommt jetzt sein eigenes `Embedding` (`training_image_id`-FK, neu), statt
  dass alle Bild-Embeddings einer Person zu einem einzigen Durchschnittsvektor verrechnet
  werden. `find_best_match` vergleicht per Cosine-Similarity gegen einen In-Prozess-Cache
  aller Bild-Embeddings, nimmt die Top-`knn_k` (Default 5) und entscheidet per
  Mehrheitsvotum. Ein einzelnes schlechtes Trainingsbild verzerrt dadurch nicht mehr dauerhaft
  das Ergebnis der ganzen Person. Nebenbei behoben: Enthielt ein Trainingsfoto mehrere
  Gesichter (z. B. eine Person im Hintergrund), floss bisher jedes davon ins Training ein —
  jetzt wird nur noch das größte erkannte Gesicht verwendet.
- Feature (Sicherheitsabstand zwischen Kandidaten): `find_best_match` prüft zusätzlich zur
  Ähnlichkeits-Schwelle jetzt den Abstand (Margin) zum besten Treffer einer *anderen* Person
  (`similarity_margin_min`, Default 0.05). Zwei sich ähnliche Personen mit knappem Vorsprung
  werden dadurch nicht mehr fälschlich als "sicherer" Treffer gemeldet, sondern auf
  "uncertain"/"unknown" zurückgestuft.
- Feature (Ausreißer-Erkennung beim Training): Nach dem Training vergleicht
  `compute_person_embedding` jedes Trainingsbild einer Person per Leave-one-out gegen den
  Mittelwert der übrigen Bilder dieser Person (mindestens `outlier_min_images`, Default 3,
  nötig). Liegt die Ähnlichkeit unter `outlier_similarity_threshold` (Default 0.30), wird
  `"outlier"` an die bestehende `TrainingImage.quality_warning`-Spalte angehängt und erscheint
  als Warn-Badge in der Personen-Ansicht — z. B. bei einem versehentlich falsch zugeordneten
  Foto oder einer extremen Kopfhaltung.
- Feature (Mehrfach-Crop-Konsens): Statt nur den Gesichts-Crop mit der höchsten
  Einzel-Konfidenz zu verwenden, wertet `main.py` jetzt alle von Frigate gelieferten Crops
  eines Events gemeinsam aus (`_analyze_crops_for_consensus`). Erst wenn mindestens
  `consensus_min_crops` (Default 2) Crops übereinstimmend dieselbe Person erkennen, gilt das
  Ergebnis als gesichert. Ist nur ein Crop verfügbar (z. B. sehr kurzer Auftritt), greift ein
  strengerer Fallback-Schwellwert (`consensus_fallback_margin_min`, Default 0.15). Ein
  einzelner Ausreißer-Crop löst dadurch keine falsche Meldung mehr aus.
- Feature (Event-Bild-Review mit Trainieren/Ablehnen): Die Events-Seite zeigt jetzt pro
  Ereignis das tatsächlich von der KI analysierte Bild an (`RecognitionEvent.snapshot_path`,
  bisher ungenutzte Spalte, wird jetzt befüllt). Bei "richtig erkannt" übernimmt „Trainieren"
  das Bild als neues Trainingsbild der ausgewählten Person; bei "falsch erkannt" markiert
  „Falsch erkannt" das Ereignis als bekannten Fehltreffer, ohne ein Trainingsbild anzulegen
  ("Anti-Training"). Neue Endpunkte `GET /api/recognition/events/{id}/image`,
  `POST /api/recognition/events/{id}/confirm`, `POST /api/recognition/events/{id}/reject`.
  Alte Snapshots werden nach `frigate_snapshot_retention_hours` (Default 24) automatisch
  aufgeräumt — diese Einstellung existierte bisher folgenlos.

## 1.0.16

- Fix (stiller Fehlerfall bei MQTT-Verbindungsabbruch): `ha_discovery.py` setzt jetzt
  `availability_topic`/`payload_available`/`payload_not_available` für alle drei Sensoren.
  `mqtt_service.py` registriert ein Last-Will (`will_set`) beim Verbinden und publiziert
  explizit "online"/"offline" bei Connect/Disconnect. Stürzt der Container ab oder bricht die
  MQTT-Verbindung unsauber ab, zeigt Home Assistant die Sensoren jetzt als "nicht verfügbar"
  statt stumm den letzten erkannten Namen stehen zu lassen.
- Feature: Icon (`icon.png`, 128×128) und Logo (`logo.png`, 256×256) fürs Add-on-Store-Card
  ergänzt.
- Feature (Bildqualitäts-Check vor Training): Neue Heuristik `FaceEngine.assess_quality`
  (Unschärfe via Laplacian-Varianz, Kontrast via Graustufen-Standardabweichung, Schwellwerte
  konfigurierbar über `quality_blur_threshold`/`quality_contrast_threshold`). Läuft beim
  Bild-Upload und bei beiden Frigate-Import-Wegen; Ergebnis landet in der neuen Spalte
  `TrainingImage.quality_warning` (Migration in `database.py`) und wird in der Personen-Ansicht
  als Warn-Badge angezeigt. Blockiert nichts — rein informativ.
- Feature (Batch-Training): Neuer Endpoint `POST /api/training/batch` trainiert alle Personen
  mit mindestens einem Trainingsbild in einem Aufruf; "Train All"-Button auf der
  Training-Seite.
- Feature (Statistik-Dashboard): Neue Seite „Stats" mit Gesamtzahlen (Events, Ø-Konfidenz,
  trainierte/Gesamt-Personen), Aufschlüsselung nach Person und Kamera sowie Verlauf der letzten
  14 Tage. Neuer Endpoint `GET /api/stats`, ohne zusätzliche Frontend-Abhängigkeit (reine
  CSS-Balken statt Chart-Library).
- Feature (Gesichts-Clustering beim Frigate-Import): Neuer Endpoint
  `GET /api/frigate/snapshots/clusters` gruppiert die Personen-Ereignis-Vorschau anhand von
  Gesichtsähnlichkeit (Schwellwert konfigurierbar über `cluster_similarity_threshold`) —
  rein zur Laufzeit berechnet, nichts wird dauerhaft gespeichert (Frigate behält die
  zugrundeliegenden Schnappschüsse ohnehin unabhängig von diesem Add-on). Im Reiter
  „Personen-Ereignisse" per Checkbox „Gruppieren" aktivierbar; pro Gruppe lässt sich die
  komplette Auswahl mit einem Klick markieren statt jedes Bild einzeln anzuklicken.

## 1.0.15

- Fix (Nutzer-Anforderung: Erkennung muss in Echtzeit UND zuverlässig sein UND darf niemals
  zweimal für dieselbe Anwesenheit melden — bisher konnte die schnelle, unsichere
  "new"-Erkennung und die spätere, zuverlässige "end"-Verfeinerung beide unabhängig
  publizieren, wodurch z. B. eine Begrüßungs-Automatisierung zweimal auslöste): `main.py`
  behandelt jetzt zusätzlich Frigates häufige `"update"`-Events (bisher verworfen), die
  während des laufenden Trackings gesendet werden. Neue Funktion `on_frigate_event_update`
  prüft darüber (gedrosselt, Default alle 2 s, konfigurierbar über
  `frigate_update_check_interval_seconds`) Frigates `/api/faces`-train-Bucket auf bereits
  verfügbare Gesichts-Crops — die dieselbe Qualität wie am `"end"`-Event liefern, aber oft
  schon Sekunden nach Bildeintritt vorliegen, statt erst wenn die Person das Bild wieder
  verlässt. `RecognitionEvent` bekommt eine neue Spalte `notified` (Migration in
  `database.py`): Sobald einmal publiziert wurde, publizieren `"new"`, `"update"` und `"end"`
  für dasselbe Frigate-Event nie wieder erneut — spätere Verfeinerungen werden weiterhin in
  der Datenbank festgehalten (korrekte Historie), aber nicht mehr an MQTT/HA gemeldet. Am
  `"new"`-Event wird außerdem nur noch publiziert, wenn das Ergebnis bereits über der
  Known-Schwelle liegt, statt jeder (auch unsicheren) Ersterkennung.

## 1.0.14

- Feature (Nutzer-Wunsch: Oberfläche soll sich in Home Assistant selbst öffnen statt in einem
  separaten Browser-Fenster): Home Assistant Ingress aktiviert (`config.yaml`: `ingress: true`,
  `ingress_port: 8000`, `panel_icon`). Der Host-Port 8000 und der `webui`-Eintrag entfallen — der
  „Open Web UI"-Button in Supervisor öffnet die App jetzt eingebettet innerhalb von Home Assistant
  (iframe), zugriffsgeschützt über die bestehende HA-Anmeldung statt eines offenen, unauthentifizierten
  Host-Ports.
  Ingress bedient die App unter einem dynamischen Pfad-Präfix (`/api/hassio_ingress/<token>/`), das
  beim Build nicht bekannt ist. Dafür im Frontend auf durchgängig relative URLs umgestellt:
  `vite.config.js` (`base: './'`, relative Asset-Pfade), `App.jsx` (`BrowserRouter` → `HashRouter`,
  da ein fester `basename` mit dem dynamischen Präfix nicht kompatibel wäre), `api.js`
  (Axios-`baseURL` ohne führenden Slash) und `EventsPage.jsx` (WebSocket-URL wird jetzt relativ zu
  `window.location.href` aufgelöst statt absolut über `/api/ws/events`). Funktioniert dadurch
  weiterhin unverändert auch im direkten docker-compose-Betrieb ohne Ingress.
- Fix (Nutzer-Meldung: beim wiederholten Import aus Frigate wurden erneut alle Bilder angeboten
  statt nur neuer): `TrainingImage` bekommt eine neue Spalte `frigate_source_filename`
  (`<frigate_name>/<filename>`, per Migration in `database.py` ergänzt). `GET /frigate/faces` und
  `GET /frigate/snapshots` filtern bereits importierte Bilder bzw. Events jetzt heraus, bevor sie
  ans Frontend gehen — ein zweiter Import-Durchlauf zeigt dadurch nur noch echte Neuzugänge.
  `POST /frigate/faces/import` und `POST /frigate/import/{event_id}` lehnen einen erneuten Import
  bereits importierter Bilder/Events zusätzlich serverseitig ab (Schutz gegen veraltete
  Frontend-Zwischenstände). Die Galerien in `FrigateImportPage.jsx` invalidieren nach einem
  erfolgreichen Import jetzt ihre jeweilige Query, damit gerade importierte Bilder sofort
  verschwinden statt erst nach einem Reload.

## 1.0.13

- Fix (Nutzer-Meldung: "Frigate hat mir richtig erkannt aber unsere App hat mich nicht erkannt" —
  live geprüft: Frigate erkannte dasselbe Event mit `sub_label_score` 0.99, unsere App lieferte
  0.03, teils sogar negative Ähnlichkeit statt eines echten, nur unscharfen Gesichts-Matches):
  Der `crop=1`-Snapshot aus 1.0.12 ist zwar auf die Personen-Bounding-Box zugeschnitten, bleibt
  aber ein Ganzkörper-Bild — das Gesicht darin ist für InsightFace' Detektor oft zu klein für eine
  brauchbare Embedding-Qualität. Frigate selbst nutzt dafür einen eigenen, dedizierten
  Gesichtsdetektor und sammelt dessen eng zugeschnittene Treffer automatisch im `train`-Bucket
  von `/api/faces` (Dateiname beginnt mit der Frigate-Event-ID). Neu: `frigate_service.py` holt
  über `get_train_face_crops(event_id)` genau diese Crops; `main.py::on_frigate_event_end`
  (ausgelöst beim `"end"`-Event, wenn Frigates Gesichtserkennung für das Event abgeschlossen ist)
  wertet sie zusätzlich zum ursprünglichen `"new"`-Snapshot aus und ersetzt das gespeicherte
  Recognition-Event durch das bessere Ergebnis, inklusive erneuter MQTT-Veröffentlichung (relevant
  für den HA-Sensor). Existierte für ein Event noch gar kein Recognition-Event (z. B. weil beim
  `"new"`-Snapshot kein Gesicht gefunden wurde), wird jetzt eines aus den Trainings-Crops
  nachträglich angelegt.
- Fix: `on_frigate_event`/`on_frigate_event_end` liefen auf dem MQTT-Hintergrundthread
  (`paho-mqtt`s `loop_forever`) ohne eigenen asyncio-Event-Loop und riefen dort
  `asyncio.create_task(...)` auf — das schlug bei jedem Frigate-Event mit
  `RuntimeError: no running event loop` fehl (im Log sichtbar, brach aber nur die
  WebSocket-Live-Aktualisierung, nicht die DB-/MQTT-Pipeline). Fix: Die Event-Loop wird beim
  Start in `main_loop` gemerkt und Broadcasts laufen jetzt über
  `asyncio.run_coroutine_threadsafe(...)` (neue Hilfsfunktion `schedule_broadcast`), die von
  jedem Thread aus sicher funktioniert.

## 1.0.12

- Verbesserung (aus der Auswertung der Frigate-Vergleichsdaten aus 1.0.11: bei 5 von 9 Events
  hatte unsere eigene Analyse gar kein Gesicht gefunden, Konfidenz 0): Der Snapshot für die
  Live-Erkennung beim `"new"`-Frigate-Event wurde bisher als volles Kamerabild abgerufen
  (`/api/events/{id}/snapshot.jpg`). Direkt beim Auftauchen im Bild ist die Person darauf oft
  noch klein/weit entfernt — schlechte Ausgangslage für InsightFace' eigenen Gesichtsdetektor.
  Fix: `frigate_service.get_snapshot()` unterstützt jetzt einen `crop`-Parameter, der Frigates
  `crop=1`-Query-Option nutzt (eng auf die Bounding-Box des erkannten Objekts zugeschnitten statt
  volles Kamerabild). Der Live-Erkennungspfad in `main.py::on_frigate_event` ruft den Snapshot
  jetzt mit `crop=True` ab. Betrifft nur die Live-MQTT-Erkennung — der Frigate-Import
  (Trainingsbilder) und die Snapshot-Vorschau im Frontend nutzen weiterhin das volle Bild.

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
