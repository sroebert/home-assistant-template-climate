"""Support for Template climates."""

from typing import TYPE_CHECKING, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.climate import (
    ENTITY_ID_FORMAT,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_MODE,
    ATTR_MAX_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_HUMIDITY,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    PRESET_ACTIVITY,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOME,
    PRESET_SLEEP,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate.const import (
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.components.template.const import CONF_AVAILABILITY_TEMPLATE
from homeassistant.components.template.helpers import async_setup_template_platform
from homeassistant.components.template.schemas import (
    make_template_entity_common_modern_attributes_schema,
)
from homeassistant.components.template.template_entity import TemplateEntity
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_ICON_TEMPLATE,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.script import Script
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_NAME, DOMAIN, LOGGER

CONF_FAN_MODE_LIST = "fan_modes"
CONF_PRESET_MODE_LIST = "preset_modes"
CONF_MODE_LIST = "modes"
CONF_SWING_MODE_LIST = "swing_modes"
CONF_TEMP_MIN_TEMPLATE = "min_temp_template"
CONF_TEMP_MIN = "min_temp"
CONF_TEMP_MAX_TEMPLATE = "max_temp_template"
CONF_TEMP_MAX = "max_temp"
CONF_PRECISION = "precision"
CONF_CURRENT_TEMP_TEMPLATE = "current_temperature_template"
CONF_TEMP_STEP = "temp_step"

CONF_CURRENT_HUMIDITY_TEMPLATE = "current_humidity_template"
CONF_MIN_HUMIDITY_TEMPLATE = "min_humidity_template"
CONF_MAX_HUMIDITY_TEMPLATE = "max_humidity_template"
CONF_TARGET_HUMIDITY_TEMPLATE = "target_humidity_template"
CONF_TARGET_TEMPERATURE_TEMPLATE = "target_temperature_template"
CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE = "target_temperature_high_template"
CONF_TARGET_TEMPERATURE_LOW_TEMPLATE = "target_temperature_low_template"
CONF_HVAC_MODE_TEMPLATE = "hvac_mode_template"
CONF_FAN_MODE_TEMPLATE = "fan_mode_template"
CONF_PRESET_MODE_TEMPLATE = "preset_mode_template"
CONF_SWING_MODE_TEMPLATE = "swing_mode_template"
CONF_HVAC_ACTION_TEMPLATE = "hvac_action_template"

CONF_SET_HUMIDITY_ACTION = "set_humidity"
CONF_SET_TEMPERATURE_ACTION = "set_temperature"
CONF_SET_HVAC_MODE_ACTION = "set_hvac_mode"
CONF_SET_FAN_MODE_ACTION = "set_fan_mode"
CONF_SET_PRESET_MODE_ACTION = "set_preset_mode"
CONF_SET_SWING_MODE_ACTION = "set_swing_mode"

CONF_CLIMATES = "climates"

BASE_HVAC_MODE_COUNT = 2

DEFAULT_TEMP = 21
DEFAULT_PRECISION = 1.0
PLATFORMS = ["climate"]

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    make_template_entity_common_modern_attributes_schema(
        CLIMATE_DOMAIN, DEFAULT_NAME
    ).schema
).extend(
    {
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        vol.Optional(CONF_ICON_TEMPLATE): cv.template,
        vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
        vol.Optional(CONF_CURRENT_TEMP_TEMPLATE): cv.template,
        vol.Optional(CONF_CURRENT_HUMIDITY_TEMPLATE): cv.template,
        vol.Optional(CONF_MIN_HUMIDITY_TEMPLATE): cv.template,
        vol.Optional(CONF_MAX_HUMIDITY_TEMPLATE): cv.template,
        vol.Optional(CONF_TARGET_HUMIDITY_TEMPLATE): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE_TEMPLATE): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE): cv.template,
        vol.Optional(CONF_TARGET_TEMPERATURE_LOW_TEMPLATE): cv.template,
        vol.Optional(CONF_HVAC_MODE_TEMPLATE): cv.template,
        vol.Optional(CONF_FAN_MODE_TEMPLATE): cv.template,
        vol.Optional(CONF_PRESET_MODE_TEMPLATE): cv.template,
        vol.Optional(CONF_SWING_MODE_TEMPLATE): cv.template,
        vol.Optional(CONF_HVAC_ACTION_TEMPLATE): cv.template,
        vol.Optional(CONF_SET_HUMIDITY_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_TEMPERATURE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_HVAC_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_FAN_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_PRESET_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(CONF_SET_SWING_MODE_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(
            CONF_MODE_LIST,
            default=[
                HVACMode.AUTO,
                HVACMode.OFF,
                HVACMode.COOL,
                HVACMode.HEAT,
                HVACMode.DRY,
                HVACMode.FAN_ONLY,
            ],
        ): cv.ensure_list,
        vol.Optional(
            CONF_FAN_MODE_LIST,
            default=[FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH],
        ): cv.ensure_list,
        vol.Optional(
            CONF_PRESET_MODE_LIST,
            default=[
                PRESET_ECO,
                PRESET_AWAY,
                PRESET_BOOST,
                PRESET_COMFORT,
                PRESET_HOME,
                PRESET_SLEEP,
                PRESET_ACTIVITY,
            ],
        ): cv.ensure_list,
        vol.Optional(
            CONF_SWING_MODE_LIST, default=[STATE_ON, HVACMode.OFF]
        ): cv.ensure_list,
        vol.Optional(CONF_TEMP_MIN_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMP_MIN, default=DEFAULT_MIN_TEMP): vol.Coerce(float),
        vol.Optional(CONF_TEMP_MAX_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMP_MAX, default=DEFAULT_MAX_TEMP): vol.Coerce(float),
        vol.Optional(CONF_PRECISION): vol.In(
            [PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]
        ),
        vol.Optional(CONF_TEMP_STEP, default=DEFAULT_PRECISION): vol.Coerce(float),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Template Climate."""
    await async_setup_reload_service(hass, DOMAIN, [CLIMATE_DOMAIN])
    await async_setup_template_platform(
        hass,
        CLIMATE_DOMAIN,
        config,
        TemplateClimate,
        None,
        async_add_entities,
        discovery_info,
        {},
    )


class TemplateClimate(TemplateEntity, ClimateEntity, RestoreEntity):
    """A template climate component."""

    _attr_should_poll = False
    _entity_id_format = ENTITY_ID_FORMAT
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(  # noqa: PLR0912, PLR0915
        self, hass: HomeAssistant, config: ConfigType, unique_id: str | None
    ) -> None:
        """Initialize the climate device."""
        super().__init__(hass, config, unique_id)

        # set attrs
        self._attr_min_temp = config[CONF_TEMP_MIN]
        self._attr_max_temp = config[CONF_TEMP_MAX]
        self._attr_target_temperature_step = config[CONF_TEMP_STEP]
        self._attr_temperature_unit = hass.config.units.temperature_unit
        self._attr_hvac_modes = config[CONF_MODE_LIST]
        self._attr_fan_modes = config[CONF_FAN_MODE_LIST]
        self._attr_preset_modes = config[CONF_PRESET_MODE_LIST]
        self._attr_swing_modes = config[CONF_SWING_MODE_LIST]
        # set optimistic default attrs
        self._attr_fan_mode = FAN_LOW
        self._attr_preset_mode = PRESET_COMFORT
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_swing_mode = HVACMode.OFF
        self._attr_target_temperature = DEFAULT_TEMP
        self._attr_target_temperature_high = None
        self._attr_target_temperature_low = None

        if (precision := config.get(CONF_PRECISION)) is not None:
            self._attr_precision = precision

        # set template properties
        self._min_temp_template = config.get(CONF_TEMP_MIN_TEMPLATE)
        self._max_temp_template = config.get(CONF_TEMP_MAX_TEMPLATE)
        self._current_temp_template = config.get(CONF_CURRENT_TEMP_TEMPLATE)
        self._current_humidity_template = config.get(CONF_CURRENT_HUMIDITY_TEMPLATE)
        self._min_humidity_template = config.get(CONF_MIN_HUMIDITY_TEMPLATE)
        self._max_humidity_template = config.get(CONF_MAX_HUMIDITY_TEMPLATE)
        self._target_humidity_template = config.get(CONF_TARGET_HUMIDITY_TEMPLATE)
        self._target_temperature_template = config.get(CONF_TARGET_TEMPERATURE_TEMPLATE)
        self._target_temperature_high_template = config.get(
            CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE
        )
        self._target_temperature_low_template = config.get(
            CONF_TARGET_TEMPERATURE_LOW_TEMPLATE
        )
        self._hvac_mode_template = config.get(CONF_HVAC_MODE_TEMPLATE)
        self._fan_mode_template = config.get(CONF_FAN_MODE_TEMPLATE)
        self._preset_mode_template = config.get(CONF_PRESET_MODE_TEMPLATE)
        self._swing_mode_template = config.get(CONF_SWING_MODE_TEMPLATE)
        self._hvac_action_template = config.get(CONF_HVAC_ACTION_TEMPLATE)

        # set turn on/off features
        if len(self._attr_hvac_modes) >= BASE_HVAC_MODE_COUNT:
            self._attr_supported_features |= ClimateEntityFeature.TURN_ON
        if HVACMode.OFF in self._attr_hvac_modes or len(self._attr_hvac_modes) > 1:
            self._attr_supported_features |= ClimateEntityFeature.TURN_OFF

        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        # set script variables
        self._set_humidity_script = None
        if set_humidity_action := config.get(CONF_SET_HUMIDITY_ACTION):
            self._set_humidity_script = Script(hass, set_humidity_action, name, DOMAIN)
            self._attr_supported_features |= ClimateEntityFeature.TARGET_HUMIDITY

        self._set_hvac_mode_script = None
        if set_hvac_mode_action := config.get(CONF_SET_HVAC_MODE_ACTION):
            self._set_hvac_mode_script = Script(
                hass, set_hvac_mode_action, name, DOMAIN
            )

        self._set_swing_mode_script = None
        if set_swing_mode_action := config.get(CONF_SET_SWING_MODE_ACTION):
            self._set_swing_mode_script = Script(
                hass, set_swing_mode_action, name, DOMAIN
            )
            self._attr_supported_features |= ClimateEntityFeature.SWING_MODE

        self._set_fan_mode_script = None
        if set_fan_mode_action := config.get(CONF_SET_FAN_MODE_ACTION):
            self._set_fan_mode_script = Script(hass, set_fan_mode_action, name, DOMAIN)
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE

        self._set_preset_mode_script = None
        if set_preset_mode_action := config.get(CONF_SET_PRESET_MODE_ACTION):
            self._set_preset_mode_script = Script(
                hass, set_preset_mode_action, name, DOMAIN
            )
            self._attr_supported_features |= ClimateEntityFeature.PRESET_MODE

        self._set_temperature_script = None
        if set_temperature_action := config.get(CONF_SET_TEMPERATURE_ACTION):
            self._set_temperature_script = Script(
                hass, set_temperature_action, name, DOMAIN
            )
            if HVACMode.HEAT_COOL in self._attr_hvac_modes:
                self._attr_supported_features |= (
                    ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
                )
                if HVACMode.OFF in self._attr_hvac_modes:
                    if len(self._attr_hvac_modes) > BASE_HVAC_MODE_COUNT:
                        # when heat_cool and off are not the only modes
                        self._attr_supported_features |= (
                            ClimateEntityFeature.TARGET_TEMPERATURE
                        )
                elif len(self._attr_hvac_modes) > 1:
                    # when heat_cool is not the only mode
                    self._attr_supported_features |= (
                        ClimateEntityFeature.TARGET_TEMPERATURE
                    )
            else:
                self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Check If we have an old state
        previous_state = await self.async_get_last_state()
        if previous_state is not None:
            if self._min_temp_template and (
                min_temp := previous_state.attributes.get(ATTR_MIN_TEMP)
            ):
                self._attr_min_temp = min_temp

            if self._max_temp_template and (
                max_temp := previous_state.attributes.get(ATTR_MAX_TEMP)
            ):
                self._attr_max_temp = max_temp

            if previous_state.state in self._attr_hvac_modes:
                self._attr_hvac_mode = HVACMode(previous_state.state)

            if temperature := previous_state.attributes.get(
                ATTR_TEMPERATURE, DEFAULT_TEMP
            ):
                self._attr_target_temperature = float(temperature)
            if temperature_high := previous_state.attributes.get(ATTR_TARGET_TEMP_HIGH):
                self._attr_target_temperature_high = float(temperature_high)
            if temperature_low := previous_state.attributes.get(ATTR_TARGET_TEMP_LOW):
                self._attr_target_temperature_low = float(temperature_low)

            self._attr_fan_mode = previous_state.attributes.get(ATTR_FAN_MODE, FAN_LOW)
            self._attr_preset_mode = previous_state.attributes.get(
                ATTR_PRESET_MODE, PRESET_COMFORT
            )
            self._attr_swing_mode = previous_state.attributes.get(
                ATTR_SWING_MODE, HVACMode.OFF
            )

            if current_temperature := previous_state.attributes.get(
                ATTR_CURRENT_TEMPERATURE
            ):
                self._attr_current_temperature = float(current_temperature)

            if humidity := previous_state.attributes.get(ATTR_CURRENT_HUMIDITY):
                self._attr_current_humidity = humidity

            if humidity := previous_state.attributes.get(ATTR_MIN_HUMIDITY):
                self._attr_min_humidity = humidity

            if humidity := previous_state.attributes.get(ATTR_MAX_HUMIDITY):
                self._attr_max_humidity = humidity

            if humidity := previous_state.attributes.get(ATTR_HUMIDITY):
                self._attr_target_humidity = humidity

    @callback
    def _async_setup_templates(self) -> None:  # noqa: PLR0912
        """Set up templates."""
        if self._min_temp_template:
            self.add_template_attribute(
                "_attr_min_temp",
                self._min_temp_template,
                None,
                self._update_min_temp,
                none_on_template_error=True,
            )

        if self._max_temp_template:
            self.add_template_attribute(
                "_attr_max_temp",
                self._max_temp_template,
                None,
                self._update_max_temp,
                none_on_template_error=True,
            )

        if self._current_temp_template:
            self.add_template_attribute(
                "_attr_current_temperature",
                self._current_temp_template,
                None,
                self._update_current_temp,
                none_on_template_error=True,
            )

        if self._current_humidity_template:
            self.add_template_attribute(
                "_attr_current_humidity",
                self._current_humidity_template,
                None,
                self._update_current_humidity,
                none_on_template_error=True,
            )

        if self._min_humidity_template:
            self.add_template_attribute(
                "_attr_min_humidity",
                self._min_humidity_template,
                None,
                self._update_min_humidity,
                none_on_template_error=True,
            )

        if self._max_humidity_template:
            self.add_template_attribute(
                "_attr_max_humidity",
                self._max_humidity_template,
                None,
                self._update_max_humidity,
                none_on_template_error=True,
            )

        if self._target_humidity_template:
            self.add_template_attribute(
                "_attr_target_humidity",
                self._target_humidity_template,
                None,
                self._update_target_humidity,
                none_on_template_error=True,
            )

        if self._target_temperature_template:
            self.add_template_attribute(
                "_attr_target_temperature",
                self._target_temperature_template,
                None,
                self._update_target_temp,
                none_on_template_error=True,
            )

        if self._target_temperature_high_template:
            self.add_template_attribute(
                "_attr_target_temperature_high",
                self._target_temperature_high_template,
                None,
                self._update_target_temp_high,
                none_on_template_error=True,
            )

        if self._target_temperature_low_template:
            self.add_template_attribute(
                "_attr_target_temperature_low",
                self._target_temperature_low_template,
                None,
                self._update_target_temp_low,
                none_on_template_error=True,
            )

        if self._hvac_mode_template:
            self.add_template_attribute(
                "_attr_hvac_mode",
                self._hvac_mode_template,
                None,
                self._update_hvac_mode,
                none_on_template_error=True,
            )
        if self._preset_mode_template:
            self.add_template_attribute(
                "_attr_preset_mode",
                self._preset_mode_template,
                None,
                self._update_preset_mode,
                none_on_template_error=True,
            )

        if self._fan_mode_template:
            self.add_template_attribute(
                "_attr_fan_mode",
                self._fan_mode_template,
                None,
                self._update_fan_mode,
                none_on_template_error=True,
            )

        if self._swing_mode_template:
            self.add_template_attribute(
                "_attr_swing_mode",
                self._swing_mode_template,
                None,
                self._update_swing_mode,
                none_on_template_error=True,
            )

        if self._hvac_action_template:
            self.add_template_attribute(
                "_hvac_action",
                self._hvac_action_template,
                None,
                self._update_hvac_action,
                none_on_template_error=True,
            )
        super()._async_setup_templates()

    @callback
    def _update_min_temp(self, temp: Any) -> None:
        if temp not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._attr_min_temp = float(temp)
            except ValueError:
                LOGGER.error("Could not parse min temperature from %s", temp)

    @callback
    def _update_max_temp(self, temp: Any) -> None:
        if temp not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._attr_max_temp = float(temp)
            except ValueError:
                LOGGER.error("Could not parse max temperature from %s", temp)

    @callback
    def _update_current_temp(self, temp: Any) -> None:
        if temp not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._attr_current_temperature = float(temp)
            except ValueError:
                LOGGER.error("Could not parse temperature from %s", temp)

    @callback
    def _update_current_humidity(self, humidity: Any) -> None:
        if humidity not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._attr_current_humidity = float(humidity)
            except ValueError:
                LOGGER.error("Could not parse humidity from %s", humidity)

    @callback
    def _update_min_humidity(self, humidity: Any) -> None:
        if humidity not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._attr_min_humidity = float(humidity)
            except ValueError:
                LOGGER.error("Could not parse min humidity from %s", humidity)

    @callback
    def _update_max_humidity(self, humidity: Any) -> None:
        if humidity not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._attr_max_humidity = float(humidity)
            except ValueError:
                LOGGER.error("Could not parse max humidity from %s", humidity)

    @callback
    def _update_target_humidity(self, humidity: Any) -> None:
        if humidity not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                new_humidity = float(humidity)
                if new_humidity != self._attr_target_humidity:
                    self._attr_target_humidity = new_humidity
                    self.async_write_ha_state()
            except ValueError:
                LOGGER.error("Could not parse target humidity from %s", humidity)

    @callback
    def _update_target_temp(self, temp: Any) -> None:
        if temp not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                new_target_temp = float(temp)
                if new_target_temp != self._attr_target_temperature:
                    self._attr_target_temperature = new_target_temp
                    self.async_write_ha_state()
            except ValueError:
                LOGGER.error("Could not parse temperature from %s", temp)

    @callback
    def _update_target_temp_high(self, temp: Any) -> None:
        if temp not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                new_target_temp_high = float(temp)
                if new_target_temp_high != self._attr_target_temperature_high:
                    self._attr_target_temperature_high = new_target_temp_high
                    self.async_write_ha_state()
            except ValueError:
                LOGGER.error("Could not parse temperature high from %s", temp)

    @callback
    def _update_target_temp_low(self, temp: Any) -> None:
        if temp not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                new_target_temp_low = float(temp)
                if new_target_temp_low != self._attr_target_temperature_low:
                    self._attr_target_temperature_low = new_target_temp_low
                    self.async_write_ha_state()
            except ValueError:
                LOGGER.error("Could not parse temperature low from %s", temp)

    @callback
    def _update_hvac_mode(self, hvac_mode_value: Any) -> None:
        if hvac_mode_value not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                hvac_mode = HVACMode(str(hvac_mode_value))
                if hvac_mode in self._attr_hvac_modes:
                    if self._attr_hvac_mode != hvac_mode:
                        self._attr_hvac_mode = hvac_mode
                        self.async_write_ha_state()
                else:
                    LOGGER.error(
                        "Received invalid hvac mode: %s. Expected: %s.",
                        hvac_mode,
                        self._attr_hvac_modes,
                    )
            except ValueError:
                LOGGER.error(
                    "Received invalid hvac mode: %s. Expected: %s.",
                    hvac_mode_value,
                    self._attr_hvac_modes,
                )

    @callback
    def _update_preset_mode(self, preset_mode_value: Any) -> None:
        preset_mode = str(preset_mode_value)
        if self._attr_preset_modes and preset_mode in self._attr_preset_modes:
            if self._attr_preset_mode != preset_mode:
                self._attr_preset_mode = preset_mode
                self.async_write_ha_state()
        elif preset_mode not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            LOGGER.error(
                "Received invalid preset mode %s. Expected %s.",
                preset_mode,
                self._attr_preset_modes,
            )

    @callback
    def _update_fan_mode(self, fan_mode_value: Any) -> None:
        fan_mode = str(fan_mode_value)
        if self._attr_fan_modes and fan_mode in self._attr_fan_modes:
            if self._attr_fan_mode != fan_mode:
                self._attr_fan_mode = fan_mode
                self.async_write_ha_state()
        elif fan_mode not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            LOGGER.error(
                "Received invalid fan mode: %s. Expected: %s.",
                fan_mode_value,
                self._attr_fan_modes,
            )

    @callback
    def _update_swing_mode(self, swing_mode_value: Any) -> None:
        swing_mode = str(swing_mode_value)
        if self._attr_swing_modes and swing_mode in self._attr_swing_modes:
            if self._attr_swing_mode != swing_mode:
                self._attr_swing_mode = swing_mode
                self.async_write_ha_state()
        elif swing_mode not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            LOGGER.error(
                "Received invalid swing mode: %s. Expected: %s.",
                swing_mode,
                self._attr_swing_modes,
            )

    @callback
    def _update_hvac_action(self, hvac_action_value: Any) -> None:
        if hvac_action_value not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                hvac_action = HVACAction(str(hvac_action_value))
                if self._attr_hvac_action != hvac_action:
                    self._attr_hvac_action = hvac_action
                    self.async_write_ha_state()
            except ValueError:
                LOGGER.error(
                    "Received invalid hvac action: %s. Expected: %s.",
                    hvac_action_value,
                    [str(member) for member in HVACAction],
                )

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return (
            self._attr_target_temperature
            if self._attr_hvac_mode != HVACMode.HEAT_COOL
            else None
        )

    @property
    def target_temperature_high(self) -> float | None:
        """Return the temperature high we try to reach."""
        return (
            self._attr_target_temperature_high
            if self._attr_hvac_mode == HVACMode.HEAT_COOL
            else None
        )

    @property
    def target_temperature_low(self) -> float | None:
        """Return the temperature low we try to reach."""
        return (
            self._attr_target_temperature_low
            if self._attr_hvac_mode == HVACMode.HEAT_COOL
            else None
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        if self._hvac_mode_template is None:
            self._attr_hvac_mode = hvac_mode  # always optimistic
            self.async_write_ha_state()

        if self._set_hvac_mode_script:
            await self.async_run_script(
                self._set_hvac_mode_script,
                run_variables={ATTR_HVAC_MODE: hvac_mode},
                context=self._context,
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self._preset_mode_template is None:
            self._attr_preset_mode = preset_mode
            self.async_write_ha_state()

        if self._set_preset_mode_script:
            await self.async_run_script(
                self._set_preset_mode_script,
                run_variables={ATTR_PRESET_MODE: preset_mode},
                context=self._context,
            )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if self._fan_mode_template is None:
            self._attr_fan_mode = fan_mode  # always optimistic
            self.async_write_ha_state()

        if self._set_fan_mode_script:
            await self.async_run_script(
                self._set_fan_mode_script,
                run_variables={ATTR_FAN_MODE: fan_mode},
                context=self._context,
            )

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        if self._swing_mode_template is None:  # use optimistic mode
            self._attr_swing_mode = swing_mode
            self.async_write_ha_state()

        if self._set_swing_mode_script:
            await self.async_run_script(
                self._set_swing_mode_script,
                run_variables={ATTR_SWING_MODE: swing_mode},
                context=self._context,
            )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature explicitly triggered by user or automation."""
        updated = False

        if kwargs.get(ATTR_HVAC_MODE, self._attr_hvac_mode) == HVACMode.HEAT_COOL:
            # Explicitly update high and low target temperatures if provided
            high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)

            if (
                high_temp is not None
                and high_temp != self._attr_target_temperature_high
            ):
                self._attr_target_temperature_high = high_temp
                updated = True

            if low_temp is not None and low_temp != self._attr_target_temperature_low:
                self._attr_target_temperature_low = low_temp
                updated = True

        else:
            # Explicitly update single target temperature if provided
            temp = kwargs.get(ATTR_TEMPERATURE)
            if temp is not None and temp != self._attr_target_temperature:
                self._attr_target_temperature = temp
                updated = True

        # Update Home Assistant state if any changes occurred
        if updated:
            self.async_write_ha_state()

        # Handle potential HVAC mode change
        if operation_mode := kwargs.get(ATTR_HVAC_MODE):
            operation_mode = HVACMode(operation_mode) if operation_mode else None
            if operation_mode and operation_mode != self._attr_hvac_mode:
                await self.async_set_hvac_mode(operation_mode)

        # Run the set temperature script if defined
        if self._set_temperature_script:
            await self.async_run_script(
                self._set_temperature_script,
                run_variables={
                    ATTR_TEMPERATURE: kwargs.get(ATTR_TEMPERATURE),
                    ATTR_TARGET_TEMP_HIGH: kwargs.get(ATTR_TARGET_TEMP_HIGH),
                    ATTR_TARGET_TEMP_LOW: kwargs.get(ATTR_TARGET_TEMP_LOW),
                    ATTR_HVAC_MODE: kwargs.get(ATTR_HVAC_MODE),
                },
                context=self._context,
            )

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        if self._target_humidity_template is None:
            self._attr_target_humidity = humidity  # always optimistic
            self.async_write_ha_state()

        if self._set_humidity_script:
            await self.async_run_script(
                self._set_humidity_script,
                run_variables={ATTR_HUMIDITY: humidity},
                context=self._context,
            )
