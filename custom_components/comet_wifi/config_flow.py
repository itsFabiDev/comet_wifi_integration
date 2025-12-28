import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback

from .const import DOMAIN, EUROTRONIC_MQTT_SERVERS

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Comet WiFi Thermostat."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step."""
        errors = {}

        if user_input is not None:
            # Validate the user input
            valid = await self._test_mqtt_connection(user_input)
            if valid:
                # Configure MQTT bridging if enabled
                if user_input.get("mqtt_bridge", True):
                    await self._configure_mqtt_bridge(user_input)
                return self.async_create_entry(title="Comet WiFi", data=user_input)
            else:
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema({
            vol.Required(CONF_HOST, default="localhost"): str,
            vol.Required(CONF_PORT, default=1883): int,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Optional("mqtt_bridge", default=True): bool,
        })

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def _test_mqtt_connection(self, data):
        """Test the MQTT connection."""
        try:
            import paho.mqtt.client as mqtt

            def on_connect(client, userdata, flags, rc):
                if rc != 0:
                    raise ConnectionError

            client = mqtt.Client()
            client.username_pw_set(data.get(CONF_USERNAME), data.get(CONF_PASSWORD))
            client.on_connect = on_connect
            client.connect(data[CONF_HOST], data[CONF_PORT], 60)
            client.loop_start()
            client.loop_stop()
            return True
        except Exception as e:
            _LOGGER.error(f"MQTT connection failed: {e}")
            return False

    async def _configure_mqtt_bridge(self, data):
        """Configure MQTT bridging to Eurotronic servers."""
        bridge_lines = [
            "connection eurotronic_bridge",
            # falls du die Server-Liste hast:
            *[f"address {server}:1883" for server in EUROTRONIC_MQTT_SERVERS],
            "topic # both 0",
            "bridge_attempt_unsubscribe false",
        ]
        bridge_config = "\n".join(bridge_lines)
    
        bridge_config_path = "/share/mosquitto/bridge.conf"
        try:
            with open(bridge_config_path, "w", encoding="utf-8") as f:
                f.write(bridge_config)
            _LOGGER.info("MQTT bridge configuration written successfully.")
        except Exception as e:
            _LOGGER.error("Failed to write MQTT bridge configuration: %s", e)


class CometWifiOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema({
            vol.Optional("mqtt_bridge", default=self.config_entry.data.get("mqtt_bridge", True)): bool,
        })

        return self.async_show_form(step_id="init", data_schema=data_schema)
