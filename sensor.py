from homeassistant.components.sensor import SensorEntity
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
        lessons = self.coordinator.data.get("timetable", {}).get(today_idx, [])
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