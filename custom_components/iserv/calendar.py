from datetime import datetime, timedelta
import logging
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        IServTimetableCalendar(coordinator, entry),
        IServEventsCalendar(coordinator, entry)
    ])

class IServTimetableCalendar(CoordinatorEntity, CalendarEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = f"{entry.title} Stundenplan"
        self._attr_unique_id = f"{entry.entry_id}_calendar_timetable"
        self._timezone = dt_util.get_default_time_zone()

    @property
    def event(self) -> CalendarEvent | None:
        events = self._get_ha_events()
        now = dt_util.now()
        for ev in sorted(events, key=lambda x: x.start):
            if ev.end > now:
                return ev
        return None

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        return [ev for ev in self._get_ha_events() if ev.start >= start_date and ev.end <= end_date]

    def _get_ha_events(self) -> list[CalendarEvent]:
        ha_events = []
        timetable = self.coordinator.data.get("timetable", {})
        now = dt_util.now()
        monday = now.date() - timedelta(days=now.weekday())
        
        for weekday_idx in range(5):
            date_obj = monday + timedelta(days=weekday_idx)
            lessons = timetable.get(weekday_idx, [])
            
            for lesson in lessons:
                try:
                    time_str = lesson.get("time", "")
                    if "-" not in time_str:
                        continue
                        
                    start_str, end_str = time_str.split("-")
                    start_time = datetime.strptime(start_str.strip(), "%H:%M").time()
                    end_time = datetime.strptime(end_str.strip(), "%H:%M").time()
                    
                    start_dt = datetime.combine(date_obj, start_time).replace(tzinfo=self._timezone)
                    end_dt = datetime.combine(date_obj, end_time).replace(tzinfo=self._timezone)
                    
                    title = lesson.get("course", "Unterricht")
                    if lesson.get("status") != "REGULÄR":
                        title = f"[{lesson.get('status')}] {title}"

                    ha_events.append(
                        CalendarEvent(
                            start=start_dt,
                            end=end_dt,
                            summary=title,
                            description=lesson.get("info", ""),
                            location=f"Raum {lesson.get('room', '')}" if lesson.get("room") else ""
                        )
                    )
                except Exception as e:
                    _LOGGER.warning("Fehler beim Parsen der Stundenplan-Zeit: %s", e)

        return ha_events

class IServEventsCalendar(CoordinatorEntity, CalendarEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = f"{entry.title} Termine"
        self._attr_unique_id = f"{entry.entry_id}_calendar_events"

    @property
    def event(self) -> CalendarEvent | None:
        events = self._get_ha_events()
        now = dt_util.now()
        for ev in sorted(events, key=lambda x: x.start):
            if ev.end > now:
                return ev
        return None

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        return [ev for ev in self._get_ha_events() if ev.start >= start_date and ev.end <= end_date]

    def _get_ha_events(self) -> list[CalendarEvent]:
        ha_events = []
        events_data = self.coordinator.data.get("events", [])
        
        for ev in events_data:
            try:
                start_raw = ev.get("start", ev.get("startDate"))
                end_raw = ev.get("end", ev.get("endDate"))
                if not start_raw:
                    continue

                end_raw = end_raw or start_raw 
                start_dt = dt_util.parse_datetime(start_raw) or dt_util.as_local(datetime.fromisoformat(start_raw))
                end_dt = dt_util.parse_datetime(end_raw) or dt_util.as_local(datetime.fromisoformat(end_raw))

                ha_events.append(
                    CalendarEvent(
                        start=start_dt,
                        end=end_dt,
                        summary=ev.get("title", ev.get("subject", "Unbekannter Termin")),
                        location=ev.get("location", "")
                    )
                )
            except Exception as e:
                pass

        return ha_events