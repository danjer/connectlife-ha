"""Tests for ConnectLife button write maps."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.connectlife.button import ConnectLifeButton


def _coordinator(appliance: SimpleNamespace) -> SimpleNamespace:
    sent: list[tuple[dict, dict]] = []

    async def async_update_device(device_id, command, properties):
        sent.append((command, properties))

    return SimpleNamespace(
        data={appliance.device_id: appliance},
        config_entry=SimpleNamespace(options={}, entry_id="e"),
        hass=None,
        last_update_success=True,
        add_entity=lambda *a, **k: None,
        async_update_device=async_update_device,
        sent=sent,
    )


def _appliance(status_list: dict[str, int]) -> SimpleNamespace:
    return SimpleNamespace(
        device_id="dev1",
        device_nickname="Dishwasher",
        device_feature_name="dishwasher",
        device_type_code="015",
        device_feature_code="dishwasher-60.3",
        room_name="Kitchen",
        status_list=status_list,
    )


@pytest.fixture
def start_button(build_dictionary):
    """A start button whose write map mixes fixed values and status references."""

    def _build(status_list: dict[str, int]):
        dictionary = build_dictionary(
            base={
                "buttons": [
                    {
                        "key": "start",
                        "write": {
                            "Actions": 2,
                            "Selected_program_id": {"from": "Selected_program_id_status"},
                            "Program_mode": {
                                "from": "Selected_program_mode",
                                "adjust": 1,
                            },
                        },
                    }
                ],
                "properties": [],
            },
        )
        appliance = _appliance(status_list)
        coordinator = _coordinator(appliance)
        return coordinator, ConnectLifeButton(coordinator, appliance, dictionary.buttons[0])

    return _build


async def test_press_reads_write_values_from_status(start_button) -> None:
    """A `from` entry sends the property's current value, less `adjust` — so the
    device is told which program to start rather than just "start"."""
    coordinator, button = start_button(
        {"Selected_program_id_status": 3, "Selected_program_mode": 2}
    )

    await button.async_press()

    command, properties = coordinator.sent[0]
    assert command == {
        "Actions": 2,
        "Selected_program_id": 3,
        "Program_mode": 1,
    }
    # Only read-back properties are reflected optimistically: the write-only
    # Actions key and the command aliases must not linger in status_list.
    assert properties == {}


async def test_press_omits_unreported_status(start_button) -> None:
    """An appliance that does not report the property still gets the rest of the
    command, rather than a bogus value or no command at all."""
    coordinator, button = start_button({"Selected_program_id_status": 3})

    await button.async_press()

    command, _ = coordinator.sent[0]
    assert command == {"Actions": 2, "Selected_program_id": 3}
