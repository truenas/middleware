from unittest.mock import Mock, patch

from middlewared.plugins.enclosure_.nvme import EnclosureService


def test__m_series_nvme_enclosures(fs):
    fs.create_file("/sys/bus/pci/slots/0-1/address", contents="0000:60:00\n")
    with patch("middlewared.plugins.enclosure_.nvme.Context") as Context:
        Context.return_value = Mock(
            list_devices=Mock(
                return_value=[
                    Mock(
                        attributes={"path": b"\\_SB_.PC03.BR3A"},
                        sys_path="/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:03/device:c5",
                    ),
                ],
            )
        )

        with patch("middlewared.plugins.enclosure_.nvme.Devices") as Devices:
            child = Mock(sys_name="nvme1")
            child.parent = Mock(sys_name="0000:60:00.0")
            Devices.from_path = Mock(
                side_effect=lambda context, path: {
                    "/sys/devices/LNXSYSTM:00/LNXSYBUS:00/PNP0A08:03/device:c5/physical_node": Mock(
                        children=[child]
                    )
                }[path],
            )

            es = EnclosureService(Mock())
            es.middleware = Mock()
            es.middleware.call_sync = Mock(return_value={'system-product-name': 'TRUENAS-M60-HA'})
            es.fake_nvme_enclosure = Mock()
            es.map_nvme()

            es.fake_nvme_enclosure.assert_called_once_with(
                "m60_plx_enclosure",
                "Rear NVME U.2 Hotswap Bays",
                "M60 Series",
                4,
                {1: "nvme1"},
            )
