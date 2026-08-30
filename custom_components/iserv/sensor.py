from datetime import datetime, timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        IServCurrentLessonSensor(coordinator, entry),
        IServExamsSensor(coordinator, entry),
        IServGradesSensor(coordinator, entry),
        IServSchoolEventsSensor(coordinator, entry),
        IServTimetableChangesSensor(coordinator, entry),
        IServTimetableSummarySensor(coordinator, entry, 0, "Stundenplan heute"),
        IServTimetableSummarySensor(coordinator, entry, 1, "Stundenplan morgen"),
        IServDaysUntilExamSensor(coordinator, entry),
        IServWeeklyPlanSensor(coordinator, entry),
        IServFeatureSensor(coordinator, entry, "notifications", "Benachrichtigungen", "mdi:bell"),
        IServMailSensor(coordinator, entry)
    ]
    async_add_entities(entities)


# --- Hilfsfunktion für Kalender-Events ---
def _get_parsed_events(coordinator):
    events = coordinator.data.get("events", [])
    parsed = []
    for ev in events:
        start_raw = ev.get("start", ev.get("startDate"))
        if not start_raw: continue
        start_dt = dt_util.parse_datetime(start_raw) or dt_util.as_local(datetime.fromisoformat(start_raw))
        title = ev.get("title", ev.get("subject", "Unbekannt"))
        is_exam = any(k in title.lower() for k in ["klausur", "arbeit", "test", "prüfung"])
        parsed.append({"title": title, "start": start_dt, "is_exam": is_exam})
    return sorted(parsed, key=lambda x: x["start"])


# 1. Aktuelle Stunde
class IServCurrentLessonSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = f"{entry.title} Aktuelle Stunde"
        self._attr_unique_id = f"{entry.entry_id}_current_lesson"
        self._attr_icon = "mdi:clock-time-four-outline"

    @property
    def native_value(self):
        now = dt_util.now()
        if now.weekday() > 4:
            return "Wochenende"

        today_str = now.strftime("%Y-%m-%d")
        lessons = self.coordinator.data.get("timetable", {}).get(today_str, [])
        if not lessons:
            return "Schulfrei"

        now_time = now.time()
        
        try:
            first_start = datetime.strptime(lessons[0]["time"].split("-")[0].strip(), "%H:%M").time()
            last_end = datetime.strptime(lessons[-1]["time"].split("-")[1].strip(), "%H:%M").time()

            if now_time < first_start: return "Vor Unterrichtsbeginn"
            if now_time > last_end: return "Schulschluss"

            for lesson in lessons:
                time_parts = lesson.get("time", "").split("-")
                if len(time_parts) == 2:
                    start_t = datetime.strptime(time_parts[0].strip(), "%H:%M").time()
                    end_t = datetime.strptime(time_parts[1].strip(), "%H:%M").time()
                    if start_t <= now_time <= end_t:
                        status = f" [{lesson['status']}]" if lesson['status'] != "REGULÄR" else ""
                        return f"{lesson['course']}{status}"
            
            return "Pause"
        except Exception:
            return "Unbekannt"


# 2. Arbeiten (Klausuren)
class IServExamsSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = f"{entry.title} Arbeiten"
        self._attr_unique_id = f"{entry.entry_id}_exams"
        self._attr_icon = "mdi:lead-pencil"

    @property
    def native_value(self):
        events = _get_parsed_events(self.coordinator)
        now = dt_util.now()
        upcoming_exams = [e for e in events if e["is_exam"] and e["start"].date() >= now.date()]
        return len(upcoming_exams) if upcoming_exams else "Aus"

    @property
    def extra_state_attributes(self):
        events = _get_parsed_events(self.coordinator)
        now = dt_util.now()
        return {"arbeiten": [e["title"] for e in events if e["is_exam"] and e["start"].date() >= now.date()]}


# 3. Noten Gesamt
class IServGradesSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = f"{entry.title} Noten Gesamt"
        self._attr_unique_id = f"{entry.entry_id}_grades"
        self._attr_icon = "mdi:school"

    @property
    def native_value(self):
        return "Unbekannt"


# 4. Schultermine (Alle Events außer Arbeiten)
class IServSchoolEventsSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = f"{entry.title} Schultermine"
        self._attr_unique_id = f"{entry.entry_id}_school_events"
        self._attr_icon = "mdi:calendar-star"

    @property
    def native_value(self):
        events = _get_parsed_events(self.coordinator)
        now = dt_util.now()
        upcoming_events = [e for e in events if not e["is_exam"] and e["start"].date() >= now.date()]
        return len(upcoming_events) if upcoming_events else "Aus"


# 5. Stundenplan Änderungen (Heute)
class IServTimetableChangesSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = f"{entry.title} Stundenplan Änderungen"
        self._attr_unique_id = f"{entry.entry_id}_timetable_changes"
        self._attr_icon = "mdi:calendar-alert"

    @property
    def native_value(self):
        today_str = dt_util.now().strftime("%Y-%m-%d")
        lessons = self.coordinator.data.get("timetable", {}).get(today_str, [])
        changes = sum(1 for l in lessons if l["status"] != "REGULÄR")
        return changes


# 6 & 7. Stundenplan Heute / Morgen (Zusammenfassung)
class IServTimetableSummarySensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, day_offset, name):
        super().__init__(coordinator)
        self.day_offset = day_offset
        self._attr_name = f"{entry.title} {name}"
        self._attr_unique_id = f"{entry.entry_id}_timetable_summary_{day_offset}"
        self._attr_icon = "mdi:calendar-check"

    @property
    def native_value(self):
        target_date = dt_util.now() + timedelta(days=self.day_offset)
        if target_date.weekday() > 4:
            return "Wochenende"

        target_str = target_date.strftime("%Y-%m-%d")
        lessons = self.coordinator.data.get("timetable", {}).get(target_str, [])
        
        if not lessons:
            return "Schulfrei"
            
        changes = sum(1 for l in lessons if l["status"] != "REGULÄR")
        if changes == 0:
            return "Planmäßig"
        return f"{changes} Änderungen"


# 8. Tage bis nächste Arbeit
class IServDaysUntilExamSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = f"{entry.title} Tage bis nächste Arbeit"
        self._attr_unique_id = f"{entry.entry_id}_days_until_exam"
        self._attr_icon = "mdi:timer-sand"

    @property
    def native_value(self):
        events = _get_parsed_events(self.coordinator)
        now = dt_util.now().date()
        
        for ev in events:
            if ev["is_exam"]:
                ev_date = ev["start"].date()
                if ev_date >= now:
                    days = (ev_date - now).days
                    if days == 0: return "Heute"
                    if days == 1: return "1 Tag"
                    return f"{days} Tage"
        return "Unbekannt"


# 9. Wochenplan JSON (Wie bei Schulmanager)
class IServWeeklyPlanSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = f"{entry.title} Wochenplan JSON"
        self._attr_unique_id = f"{entry.entry_id}_weekly_plan"
        self._attr_icon = "mdi:code-json"

    @property
    def native_value(self):
        now = dt_util.now()
        monday = now.date() - timedelta(days=now.weekday())
        kw = now.isocalendar()[1]
        return f"KW {kw} ({monday.strftime('%Y-%m-%d')})"

    @property
    def extra_state_attributes(self):
        # Liefert den rohen Timetable (4 Wochen) als JSON-Attribute
        return {"timetable_data": self.coordinator.data.get("timetable", {})}


# --- Vorhandene Sensoren (Benachrichtigungen & E-Mails) ---
class IServFeatureSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, data_key, name, icon):
        super().__init__(coordinator)
        self.data_key = data_key
        self._attr_name = f"{entry.title} {name}"
        self._attr_unique_id = f"{entry.entry_id}_{data_key}"
        self._attr_icon = icon

    @property
    def native_value(self):
        items = self.coordinator.data.get(self.data_key, [])
        return len(items) if items else "Aus"

    @property
    def extra_state_attributes(self):
        return {"items": self.coordinator.data.get(self.data_key, [])}


class IServMailSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = f"{entry.title} Ungelesene E-Mails"
        self._attr_unique_id = f"{entry.entry_id}_emails"
        self._attr_icon = "mdi:email"

    @property
    def native_value(self):
        count = self.coordinator.data.get("email_count", 0)
        return count if count > 0 else "Aus"

    @property
    def extra_state_attributes(self):
        return {"emails": self.coordinator.data.get("emails", [])}from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        IServTimetableSensor(coordinator, entry),
        IServFeatureSensor(coordinator, entry, "events", "Termine", "mdi:calendar"),
        IServFeatureSensor(coordinator, entry, "notifications", "Benachrichtigungen", "mdi:bell"),
        IServMailSensor(coordinator, entry)
    ]
    async_add_entities(entities)

class IServTimetableSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = f"{entry.title} Stundenplan Heute"
        self._attr_unique_id = f"{entry.entry_id}_timetable_today"
        self._attr_icon = "mdi:calendar-clock"

    @property
    def native_value(self):
        today_idx = dt_util.now().weekday()
        if today_idx > 4:
            return "Wochenende"
        
        today_str = dt_util.now().strftime("%Y-%m-%d")
        lessons = self.coordinator.data.get("timetable", {}).get(today_str, [])
        return f"{len(lessons)} Stunden" if lessons else "Kein Unterricht"

    @property
    def extra_state_attributes(self):
        return {"week_timetable": self.coordinator.data.get("timetable", {})}

class IServFeatureSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, data_key, name, icon):
        super().__init__(coordinator)
        self.data_key = data_key
        self._attr_name = f"{entry.title} {name}"
        self._attr_unique_id = f"{entry.entry_id}_{data_key}"
        self._attr_icon = icon

    @property
    def native_value(self):
        items = self.coordinator.data.get(self.data_key, [])
        return len(items)

    @property
    def extra_state_attributes(self):
        return {"items": self.coordinator.data.get(self.data_key, [])}

class IServMailSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = f"{entry.title} Ungelesene E-Mails"
        self._attr_unique_id = f"{entry.entry_id}_emails"
        self._attr_icon = "mdi:email"

    @property
    def native_value(self):
        return self.coordinator.data.get("email_count", 0)

    @property
    def extra_state_attributes(self):
        return {"emails": self.coordinator.data.get("emails", [])}
