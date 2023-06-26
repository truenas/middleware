import pytest

from middlewared.utils.disks import parse_sata_or_sas_disk_temp, parse_smartctl_for_temperature_output


@pytest.mark.parametrize("stdout,temperature", [
    # ataprint.cpp
    ("190 Airflow_Temperature_Cel 0x0022   073   037   045    Old_age   Always   In_the_past 27 (3 44 30 26 0)", 27),
    ("194 Temperature_Celsius     0x0022   049   067   ---    Old_age   Always       -       51 (Min/Max 24/67)", 51),
    ("190 Airflow_Temperature_Cel 0x0022   073   037   045    Old_age   Always   In_the_past 27 (3 44 30 26 0)\n"
     "194 Temperature_Celsius     0x0022   049   067   ---    Old_age   Always       -       51 (Min/Max 24/67)", 51),
    ("194 Temperature_Internal    0x0022   100   100   000    Old_age   Always       -       26\n"
     "190 Temperature_Case        0x0022   100   100   000    Old_age   Always       -       27", 26),
    ("  7 Seek_Error_Rate         0x000f   081   060   030    Pre-fail  Always       -       126511909\n"
     "190 Airflow_Temperature_Cel 0x0022   062   053   045    Old_age   Always       -       38 (Min/Max 27/40)", 38),
    # nvmeprint.cpp
    ("Temperature:                        40 Celsius", 40),
    ("Temperature Sensor 1:               30 Celsius", 30),
    # scsiprint.cpp
    ("Current Drive Temperature:     31 C", 31),
])
def test__get_temperature(stdout, temperature):
    assert parse_smartctl_for_temperature_output(stdout) == temperature


@pytest.mark.parametrize("filename,line,result", [
    (
        "attrlog.WDC_WD30EFRX_68EUZN0-WD_WCC4N2PNTD34.ata.csv",
        "2023-06-14 06:16:14;\t1;200;0;\t3;187;5616;\t4;100;84;\t5;200;0;\t7;200;0;\t9;70;22359;\t10;100;0;\t11;100;0;\t12;100;84;\t192;200;60;193;199;5043;\t194;91;59;\t196;200;0;\t197;200;0;\t198;100;0;\t199;200;0;\t200;100;0;",
        59,
    ),
    (
        "attrlog.HGST-HUS726020AL4210-N4G21DPK.scsi.csv",
        "2023-06-14\t06:02:03;\tread-corr-by-ecc-fast;0;\tread-corr-by-ecc-delayed;9;\tread-corr-by-retry;0;\tread-total-err-corrected;9;\tread-corr-algorithm-invocations;2278941;\tread-gb-processed;77192.668;\tread-total-unc-errors;0;\twrite-corr-by-ecc-fast;0;\twrite-corr-by-ecc-delayed;41;\twrite-corr-by-retry;0;\twrite-total-err-corrected;41;\twrite-corr-algorithm-invocations;1546627;\twrite-gb-processed;229818.534;\twrite-total-unc-errors;0;\tverify-corr-by-ecc-fast;0;\tverify-corr-by-ecc-delayed;0;\tverify-corr-by-retry;0;\tverify-total-err-corrected;0;\tverify-corr-algorithm-invocations;56103;\tverify-gb-processed;0.000;\tverify-total-unc-errors;0;\tnon-medium-errors;0;\ttemperature;27;",
        27,
    ),
])
def test_parse_sata_or_sas_disk_temp(filename, line, result):
    assert parse_sata_or_sas_disk_temp(filename, line) == result
