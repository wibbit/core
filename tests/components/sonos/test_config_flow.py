"""Test the sonos config flow."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant import config_entries, core
from homeassistant.components import ssdp, zeroconf
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.sonos.const import DATA_SONOS_DISCOVERY_MANAGER, DOMAIN
from homeassistant.const import CONF_HOSTS
from homeassistant.setup import async_setup_component


async def test_user_form(
    hass: core.HomeAssistant, zeroconf_payload: zeroconf.ZeroconfServiceInfo
):
    """Test we get the user initiated form."""

    # Ensure config flow will fail if no devices discovered yet
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_found"

    # Initiate a discovery to allow config entry creation
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf_payload,
    )

    # Ensure config flow succeeds after discovery
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None
    with patch(
        "homeassistant.components.sonos.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.sonos.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Sonos"
    assert result2["data"] == {}
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_already_created(hass: core.HomeAssistant):
    """Ensure we abort a flow if the entry is already created from config."""
    config = {DOMAIN: {MP_DOMAIN: {CONF_HOSTS: "192.168.4.2"}}}
    with patch(
        "homeassistant.components.sonos.async_setup_entry",
        return_value=True,
    ):
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_zeroconf_form(
    hass: core.HomeAssistant, zeroconf_payload: zeroconf.ZeroconfServiceInfo
):
    """Test we pass Zeroconf discoveries to the manager."""

    mock_manager = hass.data[DATA_SONOS_DISCOVERY_MANAGER] = MagicMock()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf_payload,
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.sonos.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.sonos.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Sonos"
    assert result2["data"] == {}

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_manager.mock_calls) == 2


async def test_ssdp_discovery(hass: core.HomeAssistant, soco):
    """Test that SSDP discoveries create a config flow."""

    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data=ssdp.SsdpServiceInfo(
            ssdp_location=f"http://{soco.ip_address}/",
            ssdp_st="urn:schemas-upnp-org:device:ZonePlayer:1",
            ssdp_usn=f"uuid:{soco.uid}_MR::urn:schemas-upnp-org:service:GroupRenderingControl:1",
            upnp={
                ssdp.ATTR_UPNP_UDN: f"uuid:{soco.uid}",
            },
        ),
    )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    flow = flows[0]

    with patch(
        "homeassistant.components.sonos.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.sonos.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "Sonos"
    assert result["data"] == {}

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_sonos_v1(hass: core.HomeAssistant):
    """Test we pass sonos devices to the discovery manager with v1 firmware devices."""

    mock_manager = hass.data[DATA_SONOS_DISCOVERY_MANAGER] = MagicMock()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="192.168.1.107",
            addresses=["192.168.1.107"],
            port=1443,
            hostname="sonos5CAAFDE47AC8.local.",
            type="_sonos._tcp.local.",
            name="Sonos-5CAAFDE47AC8._sonos._tcp.local.",
            properties={
                "_raw": {
                    "info": b"/api/v1/players/RINCON_5CAAFDE47AC801400/info",
                    "vers": b"1",
                    "protovers": b"1.18.9",
                },
                "info": "/api/v1/players/RINCON_5CAAFDE47AC801400/info",
                "vers": "1",
                "protovers": "1.18.9",
            },
        ),
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.sonos.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.sonos.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Sonos"
    assert result2["data"] == {}

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_manager.mock_calls) == 2


async def test_zeroconf_form_not_sonos(
    hass: core.HomeAssistant, zeroconf_payload: zeroconf.ZeroconfServiceInfo
):
    """Test we abort on non-sonos devices."""
    mock_manager = hass.data[DATA_SONOS_DISCOVERY_MANAGER] = MagicMock()

    zeroconf_payload.hostname = "not-aaa"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf_payload,
    )
    assert result["type"] == "abort"
    assert result["reason"] == "not_sonos_device"
    assert len(mock_manager.mock_calls) == 0
