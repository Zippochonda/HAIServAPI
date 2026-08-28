import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
import logging

from .const import CONF_COURSE_FILTER, CONF_HOST, DOMAIN
from .iserv_lib.auth import AuthClient

_LOGGER = logging.getLogger(__name__)

class IServConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].replace("https://", "").replace("http://", "").rstrip("/")
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            def _test_auth():
                return AuthClient(username, password, host)

            try:
                await self.hass.async_add_executor_job(_test_auth)
            except Exception as e:
                _LOGGER.error("IServ Auth-Fehler: %s", e)
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(f"{username}@{host}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"IServ {username}", data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_HOST, default="gollanczschule.berlin"): str,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional(CONF_COURSE_FILTER, default=""): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)