"""Adds config flow for GarbageCollection."""
import logging
import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Dict

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import ATTR_HIDDEN, CONF_ENTITIES, CONF_NAME, WEEKDAYS
from homeassistant.core import callback

from . import const

_LOGGER = logging.getLogger(__name__)


class GarbageCollectionShared:
    """Store configuration for both YAML and config_flow."""

    def __init__(self, data):
        """Create class attributes and set initial values."""
        self._data = data.copy()
        self.name = None
        self.errors = {}
        self.data_schema = {}
        self._defaults = {
            const.CONF_FREQUENCY: const.DEFAULT_FREQUENCY,
            const.CONF_ICON_NORMAL: const.DEFAULT_ICON_NORMAL,
            const.CONF_ICON_TODAY: const.DEFAULT_ICON_TODAY,
            const.CONF_ICON_TOMORROW: const.DEFAULT_ICON_TOMORROW,
            const.CONF_VERBOSE_STATE: const.DEFAULT_VERBOSE_STATE,
            ATTR_HIDDEN: False,
            const.CONF_MANUAL: False,
            const.CONF_FIRST_MONTH: const.DEFAULT_FIRST_MONTH,
            const.CONF_LAST_MONTH: const.DEFAULT_LAST_MONTH,
            const.CONF_PERIOD: const.DEFAULT_PERIOD,
            const.CONF_FIRST_WEEK: const.DEFAULT_FIRST_WEEK,
            const.CONF_VERBOSE_FORMAT: const.DEFAULT_VERBOSE_FORMAT,
            const.CONF_DATE_FORMAT: const.DEFAULT_DATE_FORMAT,
        }

    def update_data(self, user_input: Dict):
        """Remove empty fields, and fields that should not be stored in the config."""
        self._data.update(user_input)
        for key, value in user_input.items():
            if value == "":
                del self._data[key]
        if CONF_NAME in self._data:
            self.name = self._data[CONF_NAME]
            del self._data[CONF_NAME]

    def required(self, key, options):
        """Return vol.Required."""
        if isinstance(options, dict) and key in options:
            suggested_value = options[key]
        elif key in self._data:
            suggested_value = self._data[key]
        elif key in self._defaults:
            suggested_value = self._defaults[key]
        else:
            return vol.Required(key)
        return vol.Required(key, description={"suggested_value": suggested_value})

    def optional(self, key, options):
        """Return vol.Optional."""
        if isinstance(options, dict) and key in options:
            suggested_value = options[key]
        elif key in self._data:
            suggested_value = self._data[key]
        elif key in self._defaults:
            suggested_value = self._defaults[key]
        else:
            return vol.Optional(key)
        return vol.Optional(key, description={"suggested_value": suggested_value})

    def step1_frequency(self, user_input: Dict, options=False):
        """Step 1 - choose frequency and common parameters."""
        self.errors = {}
        if user_input is not None:
            try:
                cv.icon(
                    user_input.get(const.CONF_ICON_NORMAL, const.DEFAULT_ICON_NORMAL)
                )
                cv.icon(user_input.get(const.CONF_ICON_TODAY, const.DEFAULT_ICON_TODAY))
                cv.icon(
                    user_input.get(
                        const.CONF_ICON_TOMORROW, const.DEFAULT_ICON_TOMORROW
                    )
                )
            except vol.Invalid:
                self.errors["base"] = "icon"
            try:
                const.time_text(user_input.get(const.CONF_EXPIRE_AFTER))
            except vol.Invalid:
                self.errors["base"] = "time"
            if self.errors == {}:
                self.update_data(user_input)
                return True
        self.data_schema = OrderedDict()
        # Do not show name for Options_Flow. The name cannot be changed here
        if not options:
            self.data_schema[self.required(CONF_NAME, user_input)] = str
        self.data_schema[self.required(const.CONF_FREQUENCY, user_input)] = vol.In(
            const.FREQUENCY_OPTIONS
        )
        self.data_schema[self.optional(const.CONF_ICON_NORMAL, user_input)] = str
        self.data_schema[self.optional(const.CONF_ICON_TODAY, user_input)] = str
        self.data_schema[self.optional(const.CONF_ICON_TOMORROW, user_input)] = str
        self.data_schema[self.optional(const.CONF_EXPIRE_AFTER, user_input)] = str
        self.data_schema[self.optional(const.CONF_VERBOSE_STATE, user_input)] = bool
        self.data_schema[self.optional(ATTR_HIDDEN, user_input)] = bool
        self.data_schema[self.optional(const.CONF_MANUAL, user_input)] = bool
        return False

    def step2_detail(self, user_input: Dict):
        """Step 2 - enter detail that depend on frequency."""
        self.errors = {}
        self.data_schema = {}
        if user_input is not None and user_input != {}:
            # TO DO: Checking, converting
            if self._data[const.CONF_FREQUENCY] in const.GROUP_FREQUENCY:
                user_input[CONF_ENTITIES] = string_to_list(user_input[CONF_ENTITIES])
            self.update_data(user_input)
            return True
        self.data_schema = OrderedDict()
        if self._data[const.CONF_FREQUENCY] in const.ANNUAL_FREQUENCY:
            self.data_schema[self.required(const.CONF_DATE, user_input)] = str
        elif self._data[const.CONF_FREQUENCY] in const.GROUP_FREQUENCY:
            # TO DO: Defaults from entity IDs, cv.multi_select
            self.data_schema[self.required(CONF_ENTITIES, user_input)] = cv.entity_ids
        elif self._data[const.CONF_FREQUENCY] not in const.BLANK_FREQUENCY:
            self.data_schema[
                self.required(const.CONF_COLLECTION_DAYS, user_input)
            ] = cv.multi_select(WEEKDAYS)
            self.data_schema[
                self.required(const.CONF_FIRST_MONTH, user_input)
            ] = vol.In(const.MONTH_OPTIONS)
            self.data_schema[self.required(const.CONF_LAST_MONTH, user_input)] = vol.In(
                const.MONTH_OPTIONS
            )
            if self._data[const.CONF_FREQUENCY] in const.MONTHLY_FREQUENCY:
                self.data_schema[
                    self.optional(const.CONF_WEEKDAY_ORDER_NUMBER, user_input)
                ] = vol.All(
                    cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(min=1, max=5))]
                )
                self.data_schema[
                    self.optional(const.CONF_WEEK_ORDER_NUMBER, user_input)
                ] = vol.All(
                    cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(min=1, max=5))]
                )
            if self._data[const.CONF_FREQUENCY] in const.WEEKLY_DAILY_MONTHLY:
                self.data_schema[
                    self.required(const.CONF_PERIOD, user_input)
                ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=365))
            if self._data[const.CONF_FREQUENCY] in const.WEEKLY_FREQUENCY_X:
                self.data_schema[
                    self.required(const.CONF_FIRST_WEEK, user_input)
                ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=52))
            if self._data[const.CONF_FREQUENCY] in const.DAILY_FREQUENCY:
                self.data_schema[
                    self.required(const.CONF_FIRST_DATE, user_input)
                ] = cv.date
        if self._data.get(const.CONF_VERBOSE_STATE, False):
            self.data_schema[
                self.required(const.CONF_VERBOSE_FORMAT, user_input)
            ] = cv.string
            self.data_schema[
                self.required(const.CONF_DATE_FORMAT, user_input)
            ] = cv.string
        return False

    @property
    def frequency(self):
        """Return the collection frequency."""
        try:
            return self._data[const.CONF_FREQUENCY]
        except KeyError:
            return None

    @property
    def data(self):
        """Return whole data store."""
        return self._data


@config_entries.HANDLERS.register(const.DOMAIN)
class GarbageCollectionFlowHandler(config_entries.ConfigFlow):
    """Config flow for garbage_collection."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self.shared_class = GarbageCollectionShared({"unique_id": str(uuid.uuid4())})

    async def async_step_user(
        self, user_input={}
    ):  # pylint: disable=dangerous-default-value
        """Step 1 - set general parameters."""
        next_step = self.shared_class.step1_frequency(user_input)
        if next_step:
            return await self.async_step_detail(self._import)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                self.shared_class.data_schema, extra=vol.ALLOW_EXTRA
            ),
            errors=self.shared_class.errors,
        )

    async def async_step_detail(
        self, user_input={}
    ):  # pylint: disable=dangerous-default-value
        """Step 2 - enter detail depending on frequency."""
        # TO DO: Test import
        next_step = self.shared_class.step2_detail(user_input)
        if next_step:
            return self.async_create_entry(
                title=self.shared_class.name, data=self.shared_class.data
            )
        else:
            return self.async_show_form(
                step_id="detail",
                data_schema=vol.Schema(
                    self.shared_class.data_schema, extra=vol.ALLOW_EXTRA
                ),
                errors=self.shared_class.errors,
            )

    async def async_step_import(self, user_input):  # pylint: disable=unused-argument
        """Import config from configuration.yaml."""
        _LOGGER.debug("Importing config for %s", user_input)
        self.shared_class.update_data(user_input)
        return await self.async_step_user(self._import)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return options flow handler, or empty options flow if no unique_id."""
        if config_entry.data.get("unique_id", None) is not None:
            return OptionsFlowHandler(config_entry)
        return EmptyOptions(config_entry)


# O P T I O N S   F L O W


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler."""

    def __init__(self, config_entry):
        """Create and initualize class variables."""
        self.shared_class = GarbageCollectionShared(config_entry.data)

    async def async_step_init(self, user_input=None):
        """Set genral parameters."""
        next_step = self.shared_class.step1_frequency(user_input, options=True)
        if next_step:
            return await self.async_step_detail()
        else:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(self.shared_class.data_schema),
                errors=self.shared_class.errors,
            )

    async def async_step_detail(
        self, user_input={}
    ):  # pylint: disable=dangerous-default-value
        """Step 2 - annual or group (no week days)."""
        next_step = self.shared_class.step2_detail(user_input)
        if next_step:
            return self.async_create_entry(title="", data=self.shared_class.data)
        else:
            return self.async_show_form(
                step_id="detail",
                data_schema=vol.Schema(self.shared_class.data_schema),
                errors=self.shared_class.errors,
            )


class EmptyOptions(config_entries.OptionsFlow):
    """A class for default options. Not sure why this is required."""

    def __init__(self, _):
        """Just set the config_entry parameter."""
        return


def is_month_day(date) -> bool:
    """Validate mm/dd format."""
    try:
        date = datetime.strptime(date, "%m/%d")
        return True
    except ValueError:
        return False


def is_date(date) -> bool:
    """Validate yyyy-mm-dd format."""
    if date == "":
        return True
    try:
        datetime.strptime(date, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def string_to_list(string) -> list:
    """Convert comma separated text to list."""
    if isinstance(string, list):
        return string  # Already list
    if string is None or string == "":
        return []
    return list(map(lambda x: x.strip("'\" "), string.split(",")))


def is_dates(dates) -> bool:
    """Validate list of dates (yyyy-mm-dd, yyyy-mm-dd)."""
    if dates == []:
        return True
    check = True
    for date in dates:
        if not is_date(date):
            check = False
    return check
