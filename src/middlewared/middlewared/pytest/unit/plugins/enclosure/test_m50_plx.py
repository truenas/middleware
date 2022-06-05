from unittest.mock import Mock, patch

from middlewared.plugins.enclosure_.m50_plx import EnclosureService


def test__m50_plx_enclosures(fs):
    middleware = Mock(
        call_sync=Mock(
            side_effect=lambda method, *args: {
                "system.dmidecode_info": lambda: {"system-product-name": "TRUENAS-M60"},
                "enclosure.fake_nvme_enclosure": lambda id, name, model, count, slot_to_nvme: slot_to_nvme,
            }[method](*args)
        )
    )

    fs.create_file("/sys/bus/pci/slots/0-1/address", contents="0000:60:00\n")

    with patch("middlewared.plugins.enclosure_.m50_plx.pyudev") as pyudev:
        pyudev.Context = Mock(
            return_value=Mock(
                list_devices=Mock(
                    return_value=[
                        {
                            "DEVNAME": "/dev/nvme1",
                            "DEVPATH": "/devices/pci0000:5d/0000:5d:00.0/0000:5e:00.0/0000:5f:01.0/0000:60:00.0/nvme/nvme1"
                        }
                    ],
                )
            )
        )
        pyudev.Devices = Mock(
            from_path=Mock(
                side_effect=lambda context, path: {
                    "/devices/pci0000:5d/0000:5d:00.0/0000:5e:00.0/0000:5f:01.0": {"PCI_SUBSYS_ID": "10B5:8717"},
                }[path],
            )
        )

        assert EnclosureService(middleware).m50_plx_enclosures() == {1: "nvme1"}
