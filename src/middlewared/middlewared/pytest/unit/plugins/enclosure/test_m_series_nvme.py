from unittest.mock import Mock, patch

from middlewared.plugins.enclosure_.m_series_nvme import EnclosureService


def test__m_series_nvme_enclosures(fs):
    fake_nvme_enclosure = Mock()

    middleware = Mock(
        call_sync=Mock(
            side_effect=lambda method, *args: {
                "system.dmidecode_info": lambda: {"system-product-name": "TRUENAS-M60-HA"},
                "enclosure.fake_nvme_enclosure": fake_nvme_enclosure,
            }[method](*args)
        )
    )

    fs.create_file("/sys/bus/pci/slots/0-1/address", contents="0000:60:00\n")

    with patch("middlewared.plugins.enclosure_.nvme.pyudev") as pyudev:
        pyudev.Context = Mock(
            return_value=Mock(
                list_devices=Mock(
                    return_value=[
                        Mock(
                            attributes={"path": b"\\_SB_.PC03.BR3A"},
                            sys_path="/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:03/device:c5",
                        ),
                    ],
                )
            )
        )
        child = Mock(sys_name="nvme1")
        child.parent = Mock(sys_name="0000:60:00.0")
        pyudev.Devices = Mock(
            from_path=Mock(
                side_effect=lambda context, path: {
                    "/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:03/device:c5/physical_node": Mock(
                        children=[child]
                    )
                }[path],
            )
        )

        EnclosureService(middleware).map_nvme()

        fake_nvme_enclosure.assert_called_once_with(
            "m60_plx_enclosure",
            "Rear NVME U.2 Hotswap Bays",
            "M60 Series",
            4,
            {1: "nvme1"},
        )
