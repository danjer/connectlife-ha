"""Provides a button for ConnectLife write-only actions."""

import logging

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from connectlife.appliance import ConnectLifeAppliance

from .const import DOMAIN
from .coordinator import ConnectLifeCoordinator
from .dictionaries import Button, Dictionaries, WriteFromStatus
from .entity import ConnectLifeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ConnectLife buttons."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    for appliance in coordinator.data.values():
        dictionary = Dictionaries.get_dictionary(appliance)
        async_add_entities(
            ConnectLifeButton(coordinator, appliance, button)
            for button in dictionary.buttons
        )


class ConnectLifeButton(ConnectLifeEntity, ButtonEntity):
    """Button class for ConnectLife write-only actions."""

    def __init__(
        self,
        coordinator: ConnectLifeCoordinator,
        appliance: ConnectLifeAppliance,
        button: Button,
    ):
        """Initialize the entity."""
        super().__init__(
            coordinator, appliance, f"button-{button.key}", Platform.BUTTON
        )
        self.button = button
        self.entity_description = ButtonEntityDescription(
            key=self._attr_unique_id,
            icon=button.icon,
            name=button.key.replace("_", " "),
            translation_key=self.to_translation_key(button.key),
        )

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        status_list = self.coordinator.data[self.device_id].status_list
        for name, expected in self.button.available_when.items():
            if status_list.get(name) != expected:
                return False
        return True

    @callback
    def update_state(self):
        """Buttons have no state to track."""

    async def async_press(self) -> None:
        """Send the button's write map to the device."""
        status_list = self.coordinator.data[self.device_id].status_list
        command: dict[str, int] = {}
        for name, value in self.button.write.items():
            if not isinstance(value, WriteFromStatus):
                command[name] = value
                continue
            current = status_list.get(value.status)
            if not isinstance(current, int):
                # The device does not report the property (or reports it as a
                # string): send the rest of the command rather than nothing.
                _LOGGER.warning(
                    "Cannot set %s from %s for %s: no value reported",
                    name,
                    value.status,
                    self.nickname,
                )
                continue
            command[name] = current - value.adjust
        # Only reflect read-back properties optimistically; write-only keys
        # like Actions never appear in status_list and would linger as
        # phantom values until the next poll.
        properties = {k: v for k, v in command.items() if k in status_list}
        await self.async_update_device(command, properties)
