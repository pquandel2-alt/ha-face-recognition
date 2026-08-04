# Changelog

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
