from datetime import datetime, timedelta
import email
from email import policy
import imaplib
import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_COURSE_FILTER, CONF_HOST, CONF_PASSWORD, CONF_USERNAME, DEFAULT_SCAN_INTERVAL, DOMAIN
from .iserv_lib import IServAPI

_LOGGER = logging.getLogger(__name__)

class IServDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL)
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.username = entry.data[CONF_USERNAME]
        self.password = entry.data[CONF_PASSWORD]
        self.course_filter = entry.data.get(CONF_COURSE_FILTER, "")
        self.api = None

    def _extract_body(self, msg) -> str:
        body_text = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body_text = part.get_content()
                    break
        else:
            if msg.get_content_type() == "text/plain":
                body_text = msg.get_content()
        return body_text[:250] if body_text else ""

    def _sync_fetch_data(self):
        if not self.api:
            self.api = IServAPI(self.username, self.password, self.host)

        data = {}
        now = datetime.now()

        # 1. Stundenplan (komplette Woche Mo-Fr)
        monday = now.date() - timedelta(days=now.weekday())
        api_url = f"https://{self.host}/iserv/dieschulapp/api/1.0/current-timetable/"
        params = {"date": monday.strftime("%Y-%m-%d"), "week": "true", "substitutions": "true"}
        if self.course_filter:
            params["filterBy"] = f"courseSubject.course:in({self.course_filter})"
        
        headers = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/plain, */*"}
        res = self.api._session.get(api_url, params=params, headers=headers)
        
        timetable = {i: [] for i in range(5)} # Index 0=Montag, 4=Freitag
        if res.status_code == 200:
            entries = res.json().get("entries", [])
            for entry in entries:
                weekday = entry.get("weekday")
                if weekday is None or weekday > 4:
                    continue
                
                slot = entry.get("timeTableSlot", {})
                course = entry.get("courseSubject", {}).get("subject", {}).get("name", "Unbekannt")
                room = entry.get("room", {}).get("name", "")
                sub_type = entry.get("substitutionType")
                
                status = "REGULÄR"
                if sub_type:
                    status = "ENTFALL" if sub_type == "canceled" else "VERTRETUNG"
                
                timetable[weekday].append({
                    "slot": slot.get("number", 0),
                    "time": f"{slot.get('startTime', '')}-{slot.get('endTime', '')}",
                    "course": course,
                    "room": room,
                    "status": status,
                    "info": entry.get("message", "")
                })
            
            for day in range(5):
                timetable[day].sort(key=lambda x: x["slot"])
        data["timetable"] = timetable

        # 2. Termine
        try:
            events = self.api.get_upcoming_events()
            data["events"] = events.get("events", events.get("data", [])) if isinstance(events, dict) else (events if isinstance(events, list) else [])
        except Exception:
            data["events"] = []

        # 3. Benachrichtigungen
        try:
            notifs = self.api.get_notifications()
            data["notifications"] = notifs.get("notifications", notifs.get("data", [])) if isinstance(notifs, dict) else (notifs if isinstance(notifs, list) else [])
        except Exception:
            data["notifications"] = []

        # 4. E-Mails via IMAP
        emails = []
        try:
            mail = imaplib.IMAP4_SSL(self.host, 993)
            mail.login(self.username, self.password)
            mail.select("INBOX")
            _, search_data = mail.search(None, "UNSEEN")
            msg_ids = search_data[0].split()
            for num in reversed(msg_ids[:5]):
                _, msg_data = mail.fetch(num, "(BODY.PEEK[])")
                parsed_msg = email.message_from_bytes(msg_data[0][1], policy=policy.default)
                emails.append({
                    "subject": str(parsed_msg.get("Subject", "Kein Betreff")),
                    "sender": str(parsed_msg.get("From", "Unbekannt")),
                    "date": str(parsed_msg.get("Date", "")),
                    "body": self._extract_body(parsed_msg)
                })
            mail.close()
            mail.logout()
        except Exception as e:
            _LOGGER.warning("IMAP Fehler: %s", e)
        
        data["emails"] = emails
        data["email_count"] = len(emails)

        return data

    async def _async_update_data(self):
        try:
            return await self.hass.async_add_executor_job(self._sync_fetch_data)
        except Exception as err:
            raise UpdateFailed(f"Fehler beim IServ Abruf: {err}")