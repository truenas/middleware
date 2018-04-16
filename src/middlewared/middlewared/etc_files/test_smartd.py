from mock import call, Mock, patch
import textwrap

import smartd


def test_get_devices__1():
    with patch("smartd.subprocess") as subprocess:
        subprocess.check_output.return_value = textwrap.dedent("""\
            scbus0 on ata0 bus 0:
            <VBOX HARDDISK 1.0>                at scbus0 target 1 lun 0 (ada0,pass0)
            <>                                 at scbus0 target -1 lun ffffffff ()
            scbus1 on ata1 bus 0:
            <VBOX HARDDISK 1.0>                at scbus1 target 0 lun 0 (ada1,pass1)
            <>                                 at scbus1 target -1 lun ffffffff ()
            scbus2 on camsim0 bus 0:
            <>                                 at scbus2 target -1 lun ffffffff ()
            scbus-1 on xpt0 bus 0:
            <>                                 at scbus-1 target -1 lun ffffffff (xpt0)
        """)

        assert smartd.get_devices() == {
            "ada0": {
                "driver": "ata",
                "controller_id": 0,
                "channel_no": 1,
                "lun_id": 0,
            },
            "ada1": {
                "driver": "ata",
                "controller_id": 1,
                "channel_no": 0,
                "lun_id": 0,
            }
        }


def test_get_disk_propdev__arcmsr():
    assert smartd.get_disk_propdev("ada0", {
        "driver": "arcmsrX",
        "controller_id": 1000,
        "channel_no": 100,
        "lun_id": 10,
    }) == "/dev/arcmsr1000 -d areca,811"


def test_get_disk_propdev__rr274x_3x():
    assert smartd.get_disk_propdev("ada0", {
        "driver": "rr274x_3x",
        "controller_id": 1,
        "channel_no": 2,
        "lun_id": 10,
    }) == "/dev/rr274x_3x -d hpt,2/3"


def test_get_disk_propdev__rr274x_3x__1():
    assert smartd.get_disk_propdev("ada0", {
        "driver": "rr274x_3x",
        "controller_id": 1,
        "channel_no": 18,
        "lun_id": 10,
    }) == "/dev/rr274x_3x -d hpt,2/3"


def test_get_disk_propdev__rr274x_3x__2():
    assert smartd.get_disk_propdev("ada0", {
        "driver": "rr274x_3x",
        "controller_id": 1,
        "channel_no": 10,
        "lun_id": 10,
    }) == "/dev/rr274x_3x -d hpt,2/3"


def test_get_disk_propdev__hpt():
    assert smartd.get_disk_propdev("ada0", {
        "driver": "hptX",
        "controller_id": 1,
        "channel_no": 2,
        "lun_id": 10,
    }) == "/dev/hptX -d hpt,2/3"


def test_get_disk_propdev__ciss():
    assert smartd.get_disk_propdev("ada0", {
        "driver": "cissX",
        "controller_id": 1,
        "channel_no": 2,
        "lun_id": 10,
    }) == "/dev/cissX1 -d cciss,2"


def test_get_disk_propdev__twa():
    with patch("smartd.subprocess") as subprocess:
        subprocess.check_output.return_value = "Port\n"

        assert smartd.get_disk_propdev("ada0", {
            "driver": "twaX",
            "controller_id": 1,
            "channel_no": 2,
            "lun_id": 10,
        }) == "/dev/twaX1 -d 3ware,Port"

        subprocess.check_output.assert_called_once_with(
            "/usr/local/sbin/tw_cli /c1/u2 show | egrep \"^u\" | sed -E 's/.*p([0-9]+).*/\\1/'", shell=True,
            encoding="utf8",
        )


def test_get_disk_propdev__mrsas():
    assert smartd.get_disk_propdev("ada0", {
        "driver": "mrsas",
        "controller_id": 1,
        "channel_no": 2,
        "lun_id": 10,
    }) is None


def test_get_disk__unknown_usb_bridge():
    with patch("smartd.subprocess") as subprocess:
        subprocess.run.return_value = Mock(stdout="/dev/da0: Unknown USB bridge [0x0930:0x6544 (0x100)]\n"
                                                  "Please specify device type with the -d option.")

        assert smartd.get_disk_propdev("ada0", {
            "driver": "ata",
            "controller_id": 1,
            "channel_no": 2,
            "lun_id": 10,
        }) == "/dev/ada0 -d sat"

        subprocess.run.assert_called_once_with(["smartctl", "-i", "/dev/ada0"], stdout=subprocess.PIPE,
                                               stderr=subprocess.STDOUT, encoding="utf8")


def test_get_disk__generic():
    with patch("smartd.subprocess") as subprocess:
        subprocess.run.return_value = Mock(stdout="Everything is OK")

        assert smartd.get_disk_propdev("ada0", {
            "driver": "ata",
            "controller_id": 1,
            "channel_no": 2,
            "lun_id": 10,
        }) == "/dev/ada0"


def test_ensure_smart_enabled__smart_error():
    with patch("smartd.subprocess") as subprocess:
        smartd.subprocess.run.return_value = Mock(stdout="S.M.A.R.T. Error")

        assert smartd.ensure_smart_enabled("/dev/ada0") is False

        subprocess.run.assert_called_once()


def test_ensure_smart_enabled__smart_enabled():
    with patch("smartd.subprocess") as subprocess:
        subprocess.run.return_value = Mock(stdout="SMART   Enabled")

        assert smartd.ensure_smart_enabled("/dev/ada0")

        subprocess.run.assert_called_once()


def test_ensure_smart_enabled__smart_was_disabled():
    with patch("smartd.subprocess") as subprocess:
        smartd.subprocess.run.return_value = Mock(stdout="SMART   Disabled", returncode=0)

        assert smartd.ensure_smart_enabled("/dev/ada0")

        assert subprocess.run.call_args_list == [
            call(["smartctl", "-i", "/dev/ada0"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                 encoding="utf8"),
            call(["smartctl", "-s", "on", "/dev/ada0"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                 encoding="utf8"),
        ]


def test_ensure_smart_enabled__enabling_smart_failed():
    with patch("smartd.subprocess") as subprocess:
        subprocess.run.return_value = Mock(stdout="SMART   Disabled", returncode=1)

        assert smartd.ensure_smart_enabled("/dev/ada0") is False


def test_ensure_smart_enabled__handled_propdev_properly():
    with patch("smartd.subprocess") as subprocess:
        subprocess.run.return_value = Mock(stdout="SMART   Enabled")

        assert smartd.ensure_smart_enabled("/dev/ada0 -d sat")

        subprocess.run.assert_called_once_with(
            ["smartctl", "-i", "/dev/ada0", "-d", "sat"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding="utf8",
        )


def test_annotate_disk_for_smart__skips_zvol():
    assert smartd.annotate_disk_for_smart({}, {"disk_name": "/dev/zvol1"}) is None


def test_annotate_disk_for_smart__skips_unknown_device():
    assert smartd.annotate_disk_for_smart({"/dev/ada0": {}}, {"disk_name": "/dev/ada1"}) is None


def test_annotate_disk_for_smart__skips_device_without_propdev():
    with patch("smartd.get_disk_propdev") as get_disk_propdev:
        get_disk_propdev.return_value = None
        assert smartd.annotate_disk_for_smart({"/dev/ada1": {"driver": "ata"}}, {"disk_name": "/dev/ada1"}) is None


def test_annotate_disk_for_smart__skips_device_with_unavailable_smart():
    with patch("smartd.get_disk_propdev") as get_disk_propdev:
        get_disk_propdev.return_value = "/dev/ada1 -d sat"
        with patch("smartd.ensure_smart_enabled") as ensure_smart_enabled:
            ensure_smart_enabled.return_value = False
            assert smartd.annotate_disk_for_smart({"/dev/ada1": {"driver": "ata"}}, {"disk_name": "/dev/ada1"}) is \
                None


def test_annotate_disk_for_smart():
    with patch("smartd.get_disk_propdev") as get_disk_propdev:
        get_disk_propdev.return_value = "/dev/ada1 -d sat"
        with patch("smartd.ensure_smart_enabled") as ensure_smart_enabled:
            ensure_smart_enabled.return_value = True
            assert smartd.annotate_disk_for_smart({"/dev/ada1": {"driver": "ata"}}, {"disk_name": "/dev/ada1"}) == {
                "disk_name": "/dev/ada1",
                "propdev": "/dev/ada1 -d sat",
            }


def test_get_smartd_schedule_piece__every_month():
    assert smartd.get_smartd_schedule_piece("1,2,3,4,5,6,7,8,9,10,11,12", 1, 12) == ".."


def test_get_smartd_schedule_piece__every_each_month():
    assert smartd.get_smartd_schedule_piece("*/1", 1, 12) == ".."


def test_get_smartd_schedule_piece__every_fifth_month():
    assert smartd.get_smartd_schedule_piece("*/5", 1, 12) == "(05|10)"


def test_get_smartd_schedule_piece__every_specific_month():
    assert smartd.get_smartd_schedule_piece("1,5,11", 1, 12) == "(01|05|11)"


def test_get_smartd_config():
    assert smartd.get_smartd_config({
        "propdev": "/dev/ada0 -d sat",
        "smart_powermode": "never",
        "smart_difference": 0,
        "smart_informational": 1,
        "smart_critical": 2,
        "smart_email": "",
        "smarttest_type": "S",
        "smarttest_month": "*/1",
        "smarttest_daymonth": "*/1",
        "smarttest_dayweek": "*/1",
        "smarttest_hour": "*/1",
        "disk_smartoptions": "--options",
    }) == textwrap.dedent("""\
        /dev/ada0 -d sat -n never -W 0,1,2 -m root -M exec /usr/local/www/freenasUI/tools/smart_alert.py\\
        -s S/../.././..\\
         --options""")


def test_get_smartd_config_without_schedule():
    assert smartd.get_smartd_config({
        "propdev": "/dev/ada0 -d sat",
        "smart_powermode": "never",
        "smart_difference": 0,
        "smart_informational": 1,
        "smart_critical": 2,
        "smart_email": "",
        "disk_smartoptions": "--options",
    }) == textwrap.dedent("""\
        /dev/ada0 -d sat -n never -W 0,1,2 -m root -M exec /usr/local/www/freenasUI/tools/smart_alert.py --options""")
