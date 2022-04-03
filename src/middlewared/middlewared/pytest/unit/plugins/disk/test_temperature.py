import pytest

from middlewared.plugins.disk_.temperature import get_temperature


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
    assert get_temperature(stdout) == temperature
