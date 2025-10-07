"""Support for Template climates."""

import json
import logging
from collections.abc import Callable
from enum import StrEnum
from functools import partial
from typing import TYPE_CHECKING, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components import climate
from homeassistant.components.climate import (
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_ACTIONS,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    FAN_OFF,
    FAN_ON,
    HVAC_MODES,
    SWING_HORIZONTAL_OFF,
    SWING_HORIZONTAL_ON,
    SWING_OFF,
    SWING_ON,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate.const import (
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.components.template.helpers import async_setup_template_platform
from homeassistant.components.template.schemas import (
    TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA,
    make_template_entity_common_modern_attributes_schema,
)
from homeassistant.components.template.template_entity import TemplateEntity
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_OPTIMISTIC,
    CONF_TEMPERATURE_UNIT,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.script import Script
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.unit_conversion import TemperatureConverter


class HVACFeature(StrEnum):
    """HVAC feature for climate devices."""

    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"
    TARGET_TEMPERATURE = "target_temperature"
    TARGET_TEMPERATURE_RANGE = "target_temperature_range"
    TARGET_HUMIDITY = "target_humidity"
    PRESET_MODE = "preset_mode"
    FAN_MODE = "fan_mode"
    SWING_MODE = "swing_mode"
    SWING_HORIZONTAL_MODE = "swing_horizontal_mode"


HVAC_FEATURES = [cls.value for cls in HVACFeature]

_LOGGER = logging.getLogger(__name__)

CONF_CLIMATES = "climates"
CONF_CURRENT_HUMIDITY_TEMPLATE = "current_humidity_template"
CONF_CURRENT_TEMP_TEMPLATE = "current_temperature_template"
CONF_FAN_MODE_TEMPLATE = "fan_mode_template"
CONF_FAN_MODES_LIST = "fan_modes"
CONF_HUMIDITY_INITIAL = "initial_humidity"
CONF_HUMIDITY_MAX = "max_humidity"
CONF_HUMIDITY_MIN = "min_humidity"
CONF_HVAC_ACTION_TEMPLATE = "hvac_action_template"
CONF_HVAC_FEATURES_TEMPLATE = "features_template"
CONF_HVAC_MODE_TEMPLATE = "hvac_mode_template"
CONF_MODE_LIST = "modes"
CONF_PRECISION = "precision"
CONF_PRESET_MODE_TEMPLATE = "preset_mode_template"
CONF_PRESET_MODES_LIST = "preset_modes"
CONF_SET_FAN_MODE_ACTION = "set_fan_mode"
CONF_SET_HUMIDITY_ACTION = "set_humidity"
CONF_SET_HVAC_MODE_ACTION = "set_hvac_mode"
CONF_SET_PRESET_MODE_ACTION = "set_preset_mode"
CONF_SET_SWING_HORIZONTAL_MODE_ACTION = "set_swing_horizontal_mode"
CONF_SET_SWING_MODE_ACTION = "set_swing_mode"
CONF_SET_TEMPERATURE_ACTION = "set_temperature"
CONF_SWING_HORIZONTAL_MODE_LIST = "swing_horizontal_modes"
CONF_SWING_HORIZONTAL_MODE_TEMPLATE = "swing_horizontal_mode_template"
CONF_SWING_MODE_TEMPLATE = "swing_mode_template"
CONF_SWING_MODES_LIST = "swing_modes"
CONF_TARGET_HUMIDITY_TEMPLATE = "target_humidity_template"
CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE = "target_temperature_high_template"
CONF_TARGET_TEMPERATURE_LOW_TEMPLATE = "target_temperature_low_template"
CONF_TARGET_TEMPERATURE_TEMPLATE = "target_temperature_template"
CONF_TEMP_INITIAL = "initial"
CONF_TEMP_MAX = "max_temp"
CONF_TEMP_MIN = "min_temp"
CONF_TEMP_STEP = "temp_step"
CONF_TURN_OFF_ACTION = "turn_off"
CONF_TURN_ON_ACTION = "turn_on"

ATTR_HVAC_FEATURES = "hvac_features"

DOMAIN = "template_climate"
DEFAULT_NAME = "Template Climate"


CLIMATE_SCHEMA = {
    vol.Optional(CONF_TEMP_INITIAL): vol.Coerce(float),
    vol.Optional(CONF_TEMP_MIN): vol.Coerce(float),
    vol.Optional(CONF_TEMP_MAX): vol.Coerce(float),
    vol.Optional(CONF_HUMIDITY_INITIAL): vol.Coerce(float),
    vol.Optional(CONF_HUMIDITY_MIN, default=DEFAULT_MIN_HUMIDITY): cv.positive_float,
    vol.Optional(CONF_HUMIDITY_MAX, default=DEFAULT_MAX_HUMIDITY): cv.positive_float,
    vol.Optional(CONF_PRECISION): vol.All(
        vol.Coerce(float),
        vol.In([PRECISION_TENTHS, PRECISION_HALVES, PRECISION_WHOLE]),
    ),
    vol.Optional(CONF_TEMP_STEP, default=1.0): vol.Coerce(float),
    vol.Optional(CONF_TEMPERATURE_UNIT): cv.temperature_unit,
    vol.Optional(CONF_CURRENT_TEMP_TEMPLATE): cv.template,
    vol.Optional(CONF_TARGET_TEMPERATURE_TEMPLATE): cv.template,
    vol.Optional(CONF_TARGET_TEMPERATURE_LOW_TEMPLATE): cv.template,
    vol.Optional(CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE): cv.template,
    vol.Optional(CONF_CURRENT_HUMIDITY_TEMPLATE): cv.template,
    vol.Optional(CONF_TARGET_HUMIDITY_TEMPLATE): cv.template,
    vol.Optional(CONF_HVAC_MODE_TEMPLATE): cv.template,
    vol.Optional(CONF_HVAC_ACTION_TEMPLATE): cv.template,
    vol.Optional(CONF_HVAC_FEATURES_TEMPLATE): cv.template,
    vol.Optional(CONF_PRESET_MODE_TEMPLATE): cv.template,
    vol.Optional(CONF_FAN_MODE_TEMPLATE): cv.template,
    vol.Optional(CONF_SWING_MODE_TEMPLATE): cv.template,
    vol.Optional(CONF_SWING_HORIZONTAL_MODE_TEMPLATE): cv.template,
    vol.Optional(CONF_HVAC_FEATURES_TEMPLATE): cv.template,
    vol.Optional(CONF_TURN_ON_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_TURN_OFF_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_SET_TEMPERATURE_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_SET_HUMIDITY_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_SET_HVAC_MODE_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_SET_PRESET_MODE_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_SET_FAN_MODE_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_SET_SWING_MODE_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_SET_SWING_HORIZONTAL_MODE_ACTION): cv.SCRIPT_SCHEMA,
    vol.Optional(
        CONF_MODE_LIST,
        default=[HVACMode.AUTO, HVACMode.HEAT],
    ): vol.All(cv.ensure_list, [vol.In(HVAC_MODES)]),
    vol.Optional(
        CONF_PRESET_MODES_LIST,
        default=[],
    ): vol.All(cv.ensure_list, [vol.Coerce(str)]),
    vol.Optional(
        CONF_FAN_MODES_LIST,
        default=[FAN_OFF, FAN_ON],
    ): vol.All(cv.ensure_list, [vol.Coerce(str)]),
    vol.Optional(CONF_SWING_MODES_LIST, default=[SWING_ON, SWING_OFF]): vol.All(
        cv.ensure_list, [vol.Coerce(str)]
    ),
    vol.Optional(
        CONF_SWING_HORIZONTAL_MODE_LIST,
        default=[SWING_HORIZONTAL_ON, SWING_HORIZONTAL_OFF],
    ): vol.All(cv.ensure_list, [vol.Coerce(str)]),
}

PLATFORMS = [Platform.CLIMATE]
PLATFORM_SCHEMA = (
    cv.PLATFORM_SCHEMA.extend(TEMPLATE_ENTITY_OPTIMISTIC_SCHEMA)
    .extend(
        make_template_entity_common_modern_attributes_schema(
            CLIMATE_DOMAIN, DEFAULT_NAME
        ).schema
    )
    .extend(CLIMATE_SCHEMA)
)


DEFAULT_INITIAL_TEMPERATURE = 21.0
DEFAULT_INITIAL_HUMIDITY = 50.0


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
    _entity_id_format = climate.ENTITY_ID_FORMAT

    _optimistic: bool

    _attr_hvac_features: list[str] | None = None

    _current_temp_template: Template | None = None
    _target_temperature_template: Template | None = None
    _target_temperature_low_template: Template | None = None
    _target_temperature_high_template: Template | None = None
    _current_humidity_template: Template | None = None
    _target_humidity_template: Template | None = None
    _hvac_mode_template: Template | None = None
    _hvac_action_template: Template | None = None
    _hvac_features_template: Template | None = None
    _fan_mode_template: Template | None = None
    _preset_mode_template: Template | None = None
    _swing_mode_template: Template | None = None
    _swing_horizontal_mode_template: Template | None = None

    _turn_on_script: Script | None = None
    _turn_off_script: Script | None = None
    _set_temperature_script: Script | None = None
    _set_humidity_script: Script | None = None
    _set_hvac_mode_script: Script | None = None
    _set_preset_mode_script: Script | None = None
    _set_fan_mode_script: Script | None = None
    _set_swing_mode_script: Script | None = None
    _set_swing_horizontal_mode_script: Script | None = None

    def __init__(
        self, hass: HomeAssistant, config: ConfigType, unique_id: str | None
    ) -> None:
        """Initialize the climate device."""
        super().__init__(hass, config, unique_id)

        self._init_values(config)
        self._init_templates(config)
        self._init_scripts(hass, config)
        self._init_features()
        self._init_optimistic_state(config)

    def _init_values(self, config: ConfigType) -> None:
        self._optimistic = config.get(CONF_OPTIMISTIC, False)

        if precision := config.get(CONF_PRECISION):
            self._attr_precision = precision

        self._attr_temperature_unit = config.get(
            CONF_TEMPERATURE_UNIT, self.hass.config.units.temperature_unit
        )
        if (min_temp := config.get(CONF_TEMP_MIN)) is not None:
            self._attr_min_temp = min_temp
        if (max_temp := config.get(CONF_TEMP_MAX)) is not None:
            self._attr_max_temp = max_temp
        self._attr_target_temperature_step = config[CONF_TEMP_STEP]

        self._attr_min_humidity = config[CONF_HUMIDITY_MIN]
        self._attr_max_humidity = config[CONF_HUMIDITY_MAX]

        self._attr_hvac_modes = config[CONF_MODE_LIST]
        self._attr_preset_modes = config[CONF_PRESET_MODES_LIST]
        self._attr_fan_modes = config[CONF_FAN_MODES_LIST]
        self._attr_swing_modes = config[CONF_SWING_MODES_LIST]
        self._attr_swing_horizontal_modes = config[CONF_SWING_HORIZONTAL_MODE_LIST]

    def _init_templates(self, config: ConfigType) -> None:
        self._current_temp_template = config.get(CONF_CURRENT_TEMP_TEMPLATE)
        self._target_temperature_template = config.get(CONF_TARGET_TEMPERATURE_TEMPLATE)
        self._target_temperature_low_template = config.get(
            CONF_TARGET_TEMPERATURE_LOW_TEMPLATE
        )
        self._target_temperature_high_template = config.get(
            CONF_TARGET_TEMPERATURE_HIGH_TEMPLATE
        )

        self._current_humidity_template = config.get(CONF_CURRENT_HUMIDITY_TEMPLATE)
        self._target_humidity_template = config.get(CONF_TARGET_HUMIDITY_TEMPLATE)

        self._hvac_mode_template = config.get(CONF_HVAC_MODE_TEMPLATE)
        self._hvac_action_template = config.get(CONF_HVAC_ACTION_TEMPLATE)
        self._hvac_features_template = config.get(CONF_HVAC_FEATURES_TEMPLATE)
        self._preset_mode_template = config.get(CONF_PRESET_MODE_TEMPLATE)
        self._fan_mode_template = config.get(CONF_FAN_MODE_TEMPLATE)
        self._swing_mode_template = config.get(CONF_SWING_MODE_TEMPLATE)

    def _init_script(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        action_key: str,
    ) -> Script | None:
        sequence = config.get(action_key)
        if sequence is None:
            return None

        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        return Script(hass, sequence, name, DOMAIN)

    def _init_scripts(self, hass: HomeAssistant, config: ConfigType) -> None:
        self._turn_on_script = self._init_script(hass, config, CONF_TURN_ON_ACTION)
        self._turn_off_script = self._init_script(hass, config, CONF_TURN_OFF_ACTION)
        self._set_temperature_script = self._init_script(
            hass, config, CONF_SET_TEMPERATURE_ACTION
        )
        self._set_humidity_script = self._init_script(
            hass, config, CONF_SET_HUMIDITY_ACTION
        )
        self._set_hvac_mode_script = self._init_script(
            hass, config, CONF_SET_HVAC_MODE_ACTION
        )
        self._set_preset_mode_script = self._init_script(
            hass, config, CONF_SET_PRESET_MODE_ACTION
        )
        self._set_fan_mode_script = self._init_script(
            hass, config, CONF_SET_FAN_MODE_ACTION
        )
        self._set_swing_mode_script = self._init_script(
            hass, config, CONF_SET_SWING_MODE_ACTION
        )

    def _init_features(self) -> None:
        if self._hvac_features_template is not None:
            return

        support = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF

        if (
            self._optimistic
            or self._target_temperature_template is not None
            or self._set_temperature_script is not None
        ):
            support |= ClimateEntityFeature.TARGET_TEMPERATURE

        if (
            self._optimistic
            or self._target_temperature_low_template is not None
            or self._target_temperature_high_template is not None
            or self._set_temperature_script is not None
        ):
            support |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

        if (
            self._target_humidity_template is not None
            or self._set_humidity_script is not None
        ):
            support |= ClimateEntityFeature.TARGET_HUMIDITY

        if (
            self._preset_mode_template is not None
            or self._set_preset_mode_script is not None
        ):
            support |= ClimateEntityFeature.PRESET_MODE

        if self._fan_mode_template is not None or self._set_fan_mode_script is not None:
            support |= ClimateEntityFeature.FAN_MODE

        if (
            self._swing_mode_template is not None
            or self._set_swing_mode_script is not None
        ):
            support |= ClimateEntityFeature.SWING_MODE

        if (
            self._swing_horizontal_mode_template is not None
            or self._set_swing_horizontal_mode_script is not None
        ):
            support |= ClimateEntityFeature.SWING_HORIZONTAL_MODE

        self._attr_supported_features = support

    def _init_optimistic_state(self, config: ConfigType) -> None:
        init_temp: float = config.get(
            CONF_TEMP_INITIAL,
            TemperatureConverter.convert(
                DEFAULT_INITIAL_TEMPERATURE,
                UnitOfTemperature.CELSIUS,
                self.temperature_unit,
            ),
        )
        if self._target_temperature_template is None or self._optimistic:
            self._attr_target_temperature = init_temp
        if self._target_temperature_low_template is None or self._optimistic:
            self._attr_target_temperature_low = init_temp
        if self._target_temperature_high_template is None or self._optimistic:
            self._attr_target_temperature_high = init_temp

        if self._target_humidity_template is None or self._optimistic:
            self._attr_target_humidity = config.get(
                CONF_HUMIDITY_INITIAL, DEFAULT_INITIAL_HUMIDITY
            )

        if (
            self._hvac_mode_template is None or self._optimistic
        ) and HVACMode.OFF in self.hvac_modes:
            self._attr_hvac_mode = HVACMode.OFF

        if (self._fan_mode_template is None or self._optimistic) and FAN_OFF in (
            self.fan_modes or []
        ):
            self._attr_fan_mode = FAN_OFF

        if (self._swing_mode_template is None or self._optimistic) and SWING_OFF in (
            self.swing_modes or []
        ):
            self._attr_swing_mode = SWING_OFF

        if (
            self._swing_horizontal_mode_template is None or self._optimistic
        ) and SWING_HORIZONTAL_OFF in (self.swing_horizontal_modes or []):
            self._attr_swing_horizontal_mode = SWING_HORIZONTAL_OFF

    async def async_added_to_hass(self) -> None:  # noqa: PLR0912
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is None:
            return

        last_attributes = last_state.attributes

        if (
            self._hvac_features_template is not None
            and last_attributes.get(ATTR_HVAC_FEATURES) in HVAC_FEATURES
        ):
            self._attr_hvac_features = last_attributes[ATTR_HVAC_FEATURES]
            self._update_supported_features()

        if last_state.state in self.hvac_modes:
            self._attr_hvac_mode = HVACMode(last_state.state)

        if (temp := last_attributes.get(ATTR_CURRENT_TEMPERATURE)) is not None:
            self._attr_current_temperature = temp
        if (temp := last_attributes.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = temp
        if (temp := last_attributes.get(ATTR_TARGET_TEMP_LOW)) is not None:
            self._attr_target_temperature_low = temp
        if (temp := last_attributes.get(ATTR_TARGET_TEMP_HIGH)) is not None:
            self._attr_target_temperature_high = temp

        if (humidity := last_attributes.get(ATTR_CURRENT_HUMIDITY)) is not None:
            self._attr_current_humidity = humidity
        if (humidity := last_attributes.get(ATTR_HUMIDITY)) is not None:
            self._attr_target_humidity = humidity

        if last_attributes.get(ATTR_HVAC_ACTION) in CURRENT_HVAC_ACTIONS:
            self._attr_hvac_action = HVACAction(last_attributes.get(ATTR_HVAC_ACTION))

        if last_attributes.get(ATTR_PRESET_MODE) in (self.preset_modes or []):
            self._attr_preset_mode = last_attributes[ATTR_PRESET_MODE]

        if last_attributes.get(ATTR_FAN_MODE) in (self.fan_modes or []):
            self._attr_fan_mode = last_attributes[ATTR_FAN_MODE]

        if last_attributes.get(ATTR_SWING_MODE) in (self.swing_modes or []):
            self._attr_swing_mode = last_attributes[ATTR_SWING_MODE]

        if last_attributes.get(ATTR_SWING_HORIZONTAL_MODE) in (
            self.swing_horizontal_modes or []
        ):
            self._attr_swing_horizontal_mode = last_attributes[
                ATTR_SWING_HORIZONTAL_MODE
            ]

    def _setup_template_attribute(
        self,
        attribute: str,
        template: Template | None,
        on_update: Callable[[str, Any], None],
    ) -> None:
        if not template:
            return

        self.add_template_attribute(
            attribute,
            template,
            None,
            partial(on_update, attribute),
        )

    @callback
    def _async_setup_templates(self) -> None:
        self._setup_template_attribute(
            "_attr_current_temperature", self._current_temp_template, self._update_float
        )
        self._setup_template_attribute(
            "_attr_target_temperature",
            self._target_temperature_template,
            self._update_float,
        )
        self._setup_template_attribute(
            "_attr_target_temperature_low",
            self._target_temperature_low_template,
            self._update_float,
        )
        self._setup_template_attribute(
            "_attr_target_temperature_high",
            self._target_temperature_high_template,
            self._update_float,
        )
        self._setup_template_attribute(
            "_attr_current_humidity",
            self._current_humidity_template,
            self._update_float,
        )
        self._setup_template_attribute(
            "_attr_target_humidity", self._target_humidity_template, self._update_float
        )
        self._setup_template_attribute(
            "_attr_hvac_mode",
            self._hvac_mode_template,
            partial(self._update_enum, "_attr_hvac_modes"),
        )
        self._setup_template_attribute(
            "_attr_hvac_action",
            self._hvac_action_template,
            partial(self._update_enum, CURRENT_HVAC_ACTIONS),
        )
        self._setup_template_attribute(
            "_attr_preset_mode",
            self._preset_mode_template,
            partial(self._update_enum, "_attr_preset_modes"),
        )
        self._setup_template_attribute(
            "_attr_fan_mode",
            self._fan_mode_template,
            partial(self._update_enum, "_attr_fan_modes"),
        )
        self._setup_template_attribute(
            "_attr_swing_mode",
            self._swing_mode_template,
            partial(self._update_enum, "_attr_swing_modes"),
        )
        self._setup_template_attribute(
            "_attr_swing_horizontal_mode",
            self._swing_horizontal_mode_template,
            partial(self._update_enum, "_attr_swing_horizontal_modes"),
        )
        if self._hvac_features_template is not None:
            self.add_template_attribute(
                "_attr_hvac_features",
                self._hvac_features_template,
                None,
                self._update_features,
            )

        super()._async_setup_templates()

    @callback
    def _update_float(self, attribute: str, value: Any) -> None:
        try:
            if value is None or value in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                setattr(self, attribute, None)
            else:
                setattr(self, attribute, float(value))

        except (ValueError, TypeError):
            _LOGGER.exception(
                "Received invalid %s: %s for entity %s",
                attribute,
                value,
                self.entity_id,
            )

    @callback
    def _update_enum(
        self, valid_values: str | list[str], attribute: str, value: Any
    ) -> None:
        valid_values = (
            valid_values
            if isinstance(valid_values, list)
            else getattr(self, valid_values)
        )

        if value in valid_values:
            setattr(self, attribute, value)
        elif value in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            setattr(self, attribute, None)
        else:
            _LOGGER.error(
                "Received invalid %s: %s for entity %s",
                attribute,
                value,
                self.entity_id,
            )
            setattr(self, attribute, None)

    @callback
    def _update_features(self, value: Any) -> None:
        if not value:
            self._attr_hvac_features = []
            return

        value_list: list[str] = []

        string_value = str(value)
        try:
            value_json = json.loads(string_value)
            if not isinstance(value_json, list):
                _LOGGER.error(
                    "Received invalid %s: %s for entity %s",
                    ATTR_HVAC_FEATURES,
                    string_value,
                    self.entity_id,
                )
                return

            value_list = value_json

        except ValueError:
            value_list = [string_value]

        features = []
        for feature_value in value_list:
            feature = str(feature_value)
            if feature in HVAC_FEATURES:
                features.append(feature)
            else:
                _LOGGER.error(
                    "Received invalid %s: %s for entity %s",
                    ATTR_HVAC_FEATURES,
                    feature,
                    self.entity_id,
                )

        self._attr_hvac_features = features
        self._update_supported_features()

    def _update_supported_features(self) -> None:
        features = self._attr_hvac_features or []

        support: ClimateEntityFeature = ClimateEntityFeature(0)
        if HVACFeature.TURN_ON.value in features:
            support |= ClimateEntityFeature.TURN_ON
        if HVACFeature.TURN_OFF.value in features:
            support |= ClimateEntityFeature.TURN_OFF
        if HVACFeature.TARGET_TEMPERATURE.value in features:
            support |= ClimateEntityFeature.TARGET_TEMPERATURE
        if HVACFeature.TARGET_TEMPERATURE_RANGE.value in features:
            support |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        if HVACFeature.TARGET_HUMIDITY.value in features:
            support |= ClimateEntityFeature.TARGET_HUMIDITY
        if HVACFeature.PRESET_MODE.value in features:
            support |= ClimateEntityFeature.PRESET_MODE
        if HVACFeature.FAN_MODE.value in features:
            support |= ClimateEntityFeature.FAN_MODE
        if HVACFeature.SWING_MODE.value in features:
            support |= ClimateEntityFeature.SWING_MODE
        if HVACFeature.SWING_HORIZONTAL_MODE.value in features:
            support |= ClimateEntityFeature.SWING_HORIZONTAL_MODE
        self._attr_supported_features = support

    async def async_turn_on(self) -> None:
        """Turn on the climate."""
        if self._turn_on_script:
            await self.async_run_script(
                self._turn_on_script,
                context=self._context,
            )
        else:
            await super().async_turn_on()

    async def async_turn_off(self) -> None:
        """Turn off the climate."""
        if self._turn_off_script:
            await self.async_run_script(
                self._turn_off_script,
                context=self._context,
            )
        else:
            await super().async_turn_off()

    def _set_temperature_attribute(
        self,
        temp: float | None,
        template_attribute: str,
        attribute: str,
    ) -> bool:
        if temp is None:
            return False

        if self._optimistic or getattr(self, template_attribute) is None:
            setattr(self, attribute, temp)
            return True

        return False

    def _validate_set_temperature_arguments(
        self,
        hvac_mode: HVACMode | None,
        temperature: float | None,
        temperature_low: float | None,
        temperature_high: float | None,
    ) -> None:
        is_heat_cool = hvac_mode == HVACMode.HEAT_COOL or (
            hvac_mode is None and self.hvac_mode == HVACMode.HEAT_COOL
        )

        if is_heat_cool and temperature_low is None:
            message = f"Missing {ATTR_TARGET_TEMP_LOW} value in heat_cool mode"
            raise ValueError(message)
        if is_heat_cool and temperature_high is None:
            message = f"Missing {ATTR_TARGET_TEMP_HIGH} value in heat_cool mode"
            raise ValueError(message)
        if is_heat_cool and temperature is not None:
            message = f"{ATTR_TEMPERATURE} cannot be set in heat_cool mode"
            raise ValueError(message)
        if not is_heat_cool and (
            temperature_low is not None or temperature_high is not None
        ):
            message = (
                f"{ATTR_TARGET_TEMP_LOW} and {ATTR_TARGET_TEMP_HIGH} "
                "can only be set in heat_cool mode"
            )
            raise ValueError(message)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature and optionally hvac mode."""
        hvac_mode: HVACMode | None = kwargs.get(ATTR_HVAC_MODE)
        temperature: float | None = kwargs.get(ATTR_TEMPERATURE)
        temperature_low: float | None = kwargs.get(ATTR_TARGET_TEMP_LOW)
        temperature_high: float | None = kwargs.get(ATTR_TARGET_TEMP_HIGH)

        self._validate_set_temperature_arguments(
            hvac_mode, temperature, temperature_low, temperature_high
        )

        if hvac_mode is not None and hvac_mode in self.hvac_modes:
            await self.async_set_hvac_mode(hvac_mode)

        if self._set_temperature_script:
            await self.async_run_script(
                self._set_temperature_script,
                run_variables={
                    ATTR_HVAC_MODE: hvac_mode,
                    ATTR_TEMPERATURE: temperature,
                    ATTR_TARGET_TEMP_LOW: temperature_low,
                    ATTR_TARGET_TEMP_HIGH: temperature_high,
                },
                context=self._context,
            )

        changed = False

        if (
            self._optimistic or self._target_temperature_template is None
        ) and temperature is not None:
            changed |= self._set_temperature_attribute(
                temperature,
                "_target_temperature_template",
                "_attr_target_temperature",
            )

        if (
            self._optimistic or self._target_temperature_low_template is None
        ) and temperature_low is not None:
            changed |= self._set_temperature_attribute(
                temperature_low,
                "_target_temperature_low_template",
                "_attr_target_temperature_low",
            )

        if (
            self._optimistic or self._target_temperature_high_template is None
        ) and temperature_high is not None:
            changed |= self._set_temperature_attribute(
                temperature_high,
                "_target_temperature_high_template",
                "_attr_target_temperature_high",
            )

        if changed:
            self.async_write_ha_state()

    async def async_set_humidity(self, humidity: float) -> None:
        """Set new target humidity."""
        if self._set_humidity_script:
            await self.async_run_script(
                self._set_humidity_script,
                run_variables={ATTR_HUMIDITY: humidity},
                context=self._context,
            )

        if self._optimistic or self._target_humidity_template is None:
            self._attr_target_humidity = humidity
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        if self._set_hvac_mode_script:
            await self.async_run_script(
                self._set_hvac_mode_script,
                run_variables={ATTR_HVAC_MODE: hvac_mode},
                context=self._context,
            )

        if (self._optimistic or self._hvac_mode_template is None) and (
            hvac_mode != self.hvac_mode
        ):
            self._attr_hvac_mode = hvac_mode
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if self._set_preset_mode_script:
            await self.async_run_script(
                self._set_preset_mode_script,
                run_variables={ATTR_PRESET_MODE: preset_mode},
                context=self._context,
            )

        if self._optimistic or self._preset_mode_template is None:
            self._attr_preset_mode = preset_mode
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new fan mode."""
        if self._set_fan_mode_script:
            await self.async_run_script(
                self._set_fan_mode_script,
                run_variables={ATTR_FAN_MODE: fan_mode},
                context=self._context,
            )

        if self._optimistic or self._fan_mode_template is None:
            self._attr_fan_mode = fan_mode
            self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new swing mode."""
        if self._set_swing_mode_script:
            await self.async_run_script(
                self._set_swing_mode_script,
                run_variables={ATTR_SWING_MODE: swing_mode},
                context=self._context,
            )

        if self._optimistic or self._swing_mode_template is None:
            self._attr_swing_mode = swing_mode
            self.async_write_ha_state()

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode: str) -> None:
        """Set new swing horizontal mode."""
        if self._set_swing_horizontal_mode_script:
            await self.async_run_script(
                self._set_swing_horizontal_mode_script,
                run_variables={ATTR_SWING_HORIZONTAL_MODE: swing_horizontal_mode},
                context=self._context,
            )

        if self._optimistic or self._swing_horizontal_mode_template is None:
            self._attr_swing_horizontal_mode = swing_horizontal_mode
            self.async_write_ha_state()

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self._attr_hvac_mode == HVACMode.HEAT_COOL:
            return None
        return self._attr_target_temperature

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach."""
        if self._attr_hvac_mode != HVACMode.HEAT_COOL:
            return None
        return self._attr_target_temperature_low

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach."""
        if self._attr_hvac_mode != HVACMode.HEAT_COOL:
            return None
        return self._attr_target_temperature_high

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the extra state attributes of the device."""
        if self._hvac_features_template is None:
            return None

        return {ATTR_HVAC_FEATURES: self._attr_hvac_features}
