# IServ Integration für Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Diese Custom Component integriert das Schulportal **IServ** direkt in Home Assistant. Sie ruft regelmäßig den Stundenplan, Vertretungen, Kalendertermine, Benachrichtigungen und ungelesene E-Mails ab und stellt sie als Sensoren und native Home Assistant Kalender zur Verfügung.

Die Integration orientiert sich am Stil bekannter Schul-Integrationen (wie WebUntis oder Schulmanager) und lässt sich bequem über die grafische Benutzeroberfläche (UI) einrichten.

## ✨ Funktionen

* **📅 Stundenplan & Vertretungen (4 Wochen):** 
  * Eigener Kalender für den Stundenplan (zeigt regulären Unterricht, Entfälle und Vertretungen inkl. Raum und Infos).
  * Sensor (`sensor.iserv_stundenplan_heute`), der die heutigen Stunden zählt und den kompletten Plan als JSON in den Attributen für Dashboard-Karten bereithält.
* **📆 Anstehende Termine:** 
  * Eigener Kalender für alle IServ-Termine (Klassenarbeiten, Ausflüge, etc.).
  * Sensor, der die Anzahl der anstehenden Termine anzeigt.
* **🔔 Benachrichtigungen:** 
  * Sensor, der die Anzahl der aktuellen IServ-Benachrichtigungen (Badges) anzeigt und Details in den Attributen liefert.
* **📧 Ungelesene E-Mails (via IMAP):** 
  * Sensor, der die Anzahl der ungelesenen E-Mails im Posteingang zählt.
  * In den Attributen stehen Absender, Betreff und eine kurze Vorschau der neuesten E-Mails zur Verfügung.

---

## 📥 Installation

### Methode 1: Über HACS (Empfohlen)
Da diese Integration (noch) nicht im Standard-HACS-Store ist, musst du sie als benutzerdefiniertes Repository hinzufügen:

1. Öffne **HACS** in deiner Home Assistant Oberfläche.
2. Gehe auf **Integrationen**.
3. Klicke oben rechts auf die drei Punkte und wähle **Benutzerdefinierte Repositories**.
4. Füge die URL dieses GitHub-Repositories ein und wähle als Kategorie **Integration**.
5. Klicke auf *Hinzufügen*, suche in HACS nach "IServ" und lade die Integration herunter.
6. **Starte Home Assistant neu!**

### Methode 2: Manuell
1. Lade das Repository als ZIP-Datei herunter.
2. Kopiere den Ordner `custom_components/iserv` in das Verzeichnis `custom_components` deiner Home Assistant Installation (z. B. auf deiner Synology NAS).
3. **Starte Home Assistant neu!**

---

## ⚙️ Konfiguration

Die Einrichtung erfolgt vollständig über die Benutzeroberfläche von Home Assistant (Config Flow). Es müssen keine Einträge in der `configuration.yaml` vorgenommen werden!

1. Gehe in Home Assistant zu **Einstellungen** -> **Geräte & Dienste**.
2. Klicke unten rechts auf **Integration hinzufügen**.
3. Suche nach **IServ** und wähle es aus.
4. Gib deine Zugangsdaten ein:
   * **Host:** Die URL deines IServ-Portals (z. B. `gollanczschule.berlin` oder `meineschule.de` - *ohne* https://).
   * **Benutzername:** Dein IServ-Benutzername (meist `vorname.nachname`).
   * **Passwort:** Dein IServ-Passwort (wird auch für den IMAP-Abruf genutzt).
   * **Kurs-Filter (Optional):** Hier kannst du bestimmte Kurs-IDs durch Pipe-Symbole getrennt eintragen, um den Stundenplan zu filtern (z. B. `2627690|2627709|2627761`). Lass das Feld leer, um alles abzurufen.

---

## 📊 Dashboard Beispiele (Lovelace)

Die Sensoren dieser Integration sind bewusst so aufgebaut, dass der Hauptstatus (State) kurz und knapp ist (z. B. "6 Stunden" oder "3"). Die eigentlichen Daten liegen in den **Attributen**, um sie flexibel in Dashboards nutzen zu können.

Hier sind Beispiele für **Markdown-Karten**, die du direkt in dein Dashboard einfügen kannst. *(Ersetze `sensor.iserv_max_mustermann_...` durch die tatsächlichen Namen deiner Entitäten).*

### 1. Heutiger Stundenplan
```yaml
type: markdown
title: 🏫 Stundenplan Heute
content: >
  {% set today = now().strftime('%Y-%m-%d') %}
  {% set timetable = state_attr('sensor.iserv_max_mustermann_stundenplan_heute', 'week_timetable') %}
  
  {% if timetable and timetable.get(today) %}
    {% for lesson in timetable[today] %}
      **{{ lesson.slot }}. Std ({{ lesson.time }})**: {{ lesson.course }} (Raum {{ lesson.room }})
      {% if lesson.status != 'REGULÄR' %}
        > ⚠️ **[{{ lesson.status }}]** {{ lesson.info }}
      {% endif %}
    {% endfor %}
  {% else %}
    🎉 Heute kein Unterricht eingetragen!
  {% endif %}

### 2. Ungelesene E-Mails Vorschau
```yaml
type: markdown
title: 📧 Neue IServ E-Mails
content: >
  {% set emails = state_attr('sensor.iserv_max_mustermann_ungelesene_e_mails', 'emails') %}
  
  {% if emails and emails | length > 0 %}
    {% for email in emails %}
      **Von:** {{ email.sender }}
      **Betreff:** {{ email.subject }}
      *{{ email.body | truncate(100) }}*
      ***
    {% endfor %}
  {% else %}
    Keine neuen E-Mails.
  {% endif %}

### 🛠 Fehlerbehebung
Invalid handler specified: Du hast vergessen, Home Assistant nach dem Herunterladen der Dateien neu zu starten. Bitte führe einen vollständigen Neustart durch.

Keine Stundenplandaten: Prüfe, ob dein Kurs-Filter (falls angegeben) korrekte IDs enthält.

IMAP / E-Mails werden nicht geladen: Stelle sicher, dass IMAP in deiner IServ-Instanz für deinen Account freigeschaltet ist und du das korrekte Passwort verwendest.

🤝 Danksagung
Diese Integration nutzt angepasste Teile der IServAPI https://github.com/Leo-Aqua/IServAPI für den Login und Datenabruf.
