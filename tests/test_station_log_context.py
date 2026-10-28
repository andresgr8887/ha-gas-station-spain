"""Verify failed requests identify the configured station without API metadata."""

# pylint: disable=redefined-outer-name,protected-access,unused-argument

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gas_station_spain.const import DOMAIN
from custom_components.gas_station_spain.sensor import GasStationCoordinator, async_setup_entry


@pytest.mark.parametrize("station_name", ["ARA-PETROSTAR POLIGONO", None])
async def test_update_failure_identifies_station(hass, caplog, station_name):
    """Keep the saved name, IDs and original error even if the API knows no station."""
    coordinator = GasStationCoordinator(hass, 14409, 1, station_name=station_name)
    with patch(
        "custom_components.gas_station_spain.sensor.gss.get_price",
        side_effect=ValueError("Station 14409 was not found in the Ministry data"),
    ):
        data = await coordinator._async_update_data()
    assert data["price"] is None
    assert f"Could not update {station_name or 'Gas station 14409'} (station=14409 product=1)" in caplog.text
    assert "Station 14409 was not found in the Ministry data" in caplog.text


async def test_initial_lookup_failure_identifies_station(hass, caplog, mock_get_price):
    """The configured title is available before the first successful metadata lookup."""
    coordinator = GasStationCoordinator(hass, 14409, 1, station_name="ARA-PETROSTAR POLIGONO")
    coordinator.config_entry = MockConfigEntry(domain=DOMAIN, state=ConfigEntryState.SETUP_IN_PROGRESS)
    with patch(
        "custom_components.gas_station_spain.sensor.gss.get_gas_station",
        side_effect=ValueError("Missing station"),
    ):
        await coordinator.async_config_entry_first_refresh()
    assert "Could not fetch gas station data for ARA-PETROSTAR POLIGONO (station=14409): Missing station" in caplog.text
    assert coordinator.data["price"] == 1.459


async def test_setup_passes_saved_title(hass, mock_config_entry_data, mock_get_gas_station, mock_get_price):
    """Use the user's entry title instead of depending on a Ministry response name."""
    entry = MockConfigEntry(domain=DOMAIN, title="Mi gasolinera", data=mock_config_entry_data, unique_id="1-1234")
    entry.add_to_hass(hass)
    add_entities = MagicMock()
    await async_setup_entry(hass, entry, add_entities)
    sensor = add_entities.call_args.args[0][0]
    assert sensor.coordinator._station_name == "Mi gasolinera"


async def test_initial_refresh_exception_identifies_entry(hass, mock_config_entry_data, caplog):
    """The setup fallback message also includes the title before a sensor exists."""
    entry = MockConfigEntry(domain=DOMAIN, title="Mi gasolinera", data=mock_config_entry_data, unique_id="1-1234")
    entry.add_to_hass(hass)
    with patch.object(GasStationCoordinator, "async_config_entry_first_refresh", side_effect=ValueError("Initial error")):
        await async_setup_entry(hass, entry, MagicMock())
    assert "Could not fetch initial data for Mi gasolinera (station=1234): Initial error" in caplog.text
