from unittest.mock import Mock

import pytest
import copy

from middlewared.alert.base import Alert
from middlewared.alert.source.jbof import JBOFInvalidDataAlertClass, JBOFRedfishCommAlertClass, JBOFAlertSource, JBOFElementWarningAlertClass, JBOFElementCriticalAlertClass
from middlewared.pytest.unit.middleware import Middleware

uuid1 = '244c0e5f-bf7b-4a68-bd40-80e3f1a5b4ed'
desc1 = 'ES24N - 1234'
ip1 = '1.2.3.4'
ip2 = '1.2.3.5'
jbof_query_one = [
    {
        'id': 1,
        'description': desc1,
        'index': 0,
        'uuid': uuid1,
        'mgmt_ip1': ip1,
        'mgmt_ip2': ip2,
        'mgmt_username': 'Admin',
        'mgmt_password': 'SomePassword'
    }
]
jbof1_id_dict = {'desc': desc1, 'ip1': ip1, 'ip2': ip2}

jbof_data_one = [
    {'bsg': None,
     'controller': False,
     'dmi': uuid1,
     'elements': {'Array Device Slot': {'1': {'descriptor': 'Disk #1',
                                              'dev': 'nvme25n1',
                                              'original': {'descriptor': 'slot1',
                                                           'enclosure_bsg': None,
                                                           'enclosure_id': uuid1,
                                                           'enclosure_sg': None,
                                                           'slot': 1},
                                              'status': 'OK',
                                              'value': None,
                                              'value_raw': 16777216},
                                        '10': {'descriptor': 'Disk #10',
                                               'dev': None,
                                               'original': {'descriptor': 'slot10',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 10},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '11': {'descriptor': 'Disk #11',
                                               'dev': None,
                                               'original': {'descriptor': 'slot11',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 11},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '12': {'descriptor': 'Disk #12',
                                               'dev': None,
                                               'original': {'descriptor': 'slot12',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 12},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '13': {'descriptor': 'Disk #13',
                                               'dev': None,
                                               'original': {'descriptor': 'slot13',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 13},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '14': {'descriptor': 'Disk #14',
                                               'dev': None,
                                               'original': {'descriptor': 'slot14',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 14},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '15': {'descriptor': 'Disk #15',
                                               'dev': None,
                                               'original': {'descriptor': 'slot15',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 15},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '16': {'descriptor': 'Disk #16',
                                               'dev': None,
                                               'original': {'descriptor': 'slot16',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 16},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '17': {'descriptor': 'Disk #17',
                                               'dev': None,
                                               'original': {'descriptor': 'slot17',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 17},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '18': {'descriptor': 'Disk #18',
                                               'dev': None,
                                               'original': {'descriptor': 'slot18',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 18},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '19': {'descriptor': 'Disk #19',
                                               'dev': None,
                                               'original': {'descriptor': 'slot19',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 19},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '2': {'descriptor': 'Disk #2',
                                              'dev': 'nvme27n1',
                                              'original': {'descriptor': 'slot2',
                                                           'enclosure_bsg': None,
                                                           'enclosure_id': uuid1,
                                                           'enclosure_sg': None,
                                                           'slot': 2},
                                              'status': 'OK',
                                              'value': None,
                                              'value_raw': 16777216},
                                        '20': {'descriptor': 'Disk #20',
                                               'dev': None,
                                               'original': {'descriptor': 'slot20',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 20},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '21': {'descriptor': 'Disk #21',
                                               'dev': None,
                                               'original': {'descriptor': 'slot21',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 21},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '22': {'descriptor': 'Disk #22',
                                               'dev': None,
                                               'original': {'descriptor': 'slot22',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 22},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '23': {'descriptor': 'Disk #23',
                                               'dev': None,
                                               'original': {'descriptor': 'slot23',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 23},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '24': {'descriptor': 'Disk #24',
                                               'dev': None,
                                               'original': {'descriptor': 'slot24',
                                                            'enclosure_bsg': None,
                                                            'enclosure_id': uuid1,
                                                            'enclosure_sg': None,
                                                            'slot': 24},
                                               'status': 'Not installed',
                                               'value': None,
                                               'value_raw': 83886080},
                                        '3': {'descriptor': 'Disk #3',
                                              'dev': 'nvme26n1',
                                              'original': {'descriptor': 'slot3',
                                                           'enclosure_bsg': None,
                                                           'enclosure_id': uuid1,
                                                           'enclosure_sg': None,
                                                           'slot': 3},
                                              'status': 'OK',
                                              'value': None,
                                              'value_raw': 16777216},
                                        '4': {'descriptor': 'Disk #4',
                                              'dev': None,
                                              'original': {'descriptor': 'slot4',
                                                           'enclosure_bsg': None,
                                                           'enclosure_id': uuid1,
                                                           'enclosure_sg': None,
                                                           'slot': 4},
                                              'status': 'Not installed',
                                              'value': None,
                                              'value_raw': 83886080},
                                        '5': {'descriptor': 'Disk #5',
                                              'dev': None,
                                              'original': {'descriptor': 'slot5',
                                                           'enclosure_bsg': None,
                                                           'enclosure_id': uuid1,
                                                           'enclosure_sg': None,
                                                           'slot': 5},
                                              'status': 'Not installed',
                                              'value': None,
                                              'value_raw': 83886080},
                                        '6': {'descriptor': 'Disk #6',
                                              'dev': None,
                                              'original': {'descriptor': 'slot6',
                                                           'enclosure_bsg': None,
                                                           'enclosure_id': uuid1,
                                                           'enclosure_sg': None,
                                                           'slot': 6},
                                              'status': 'Not installed',
                                              'value': None,
                                              'value_raw': 83886080},
                                        '7': {'descriptor': 'Disk #7',
                                              'dev': None,
                                              'original': {'descriptor': 'slot7',
                                                           'enclosure_bsg': None,
                                                           'enclosure_id': uuid1,
                                                           'enclosure_sg': None,
                                                           'slot': 7},
                                              'status': 'Not installed',
                                              'value': None,
                                              'value_raw': 83886080},
                                        '8': {'descriptor': 'Disk #8',
                                              'dev': None,
                                              'original': {'descriptor': 'slot8',
                                                           'enclosure_bsg': None,
                                                           'enclosure_id': uuid1,
                                                           'enclosure_sg': None,
                                                           'slot': 8},
                                              'status': 'Not installed',
                                              'value': None,
                                              'value_raw': 83886080},
                                        '9': {'descriptor': 'Disk #9',
                                              'dev': None,
                                              'original': {'descriptor': 'slot9',
                                                           'enclosure_bsg': None,
                                                           'enclosure_id': uuid1,
                                                           'enclosure_sg': None,
                                                           'slot': 9},
                                              'status': 'Not installed',
                                              'value': None,
                                              'value_raw': 83886080}},
                  'Cooling': {'Fan1': {'descriptor': 'Fan1',
                                       'status': 'OK',
                                       'value': 'SpeedRPM=21760.0',
                                       'value_raw': None},
                              'Fan2': {'descriptor': 'Fan2',
                                       'status': 'OK',
                                       'value': 'SpeedRPM=21760.0',
                                       'value_raw': None},
                              'Fan3': {'descriptor': 'Fan3',
                                       'status': 'OK',
                                       'value': 'SpeedRPM=21760.0',
                                       'value_raw': None},
                              'Fan4': {'descriptor': 'Fan4',
                                       'status': 'OK',
                                       'value': 'SpeedRPM=21792.0',
                                       'value_raw': None},
                              'Fan5': {'descriptor': 'Fan5',
                                       'status': 'OK',
                                       'value': None,
                                       'value_raw': None},
                              'Fan6': {'descriptor': 'Fan6',
                                       'status': 'OK',
                                       'value': 'SpeedRPM=21792.0',
                                       'value_raw': None}},
                  'Power Supply': {'PSU1': {'descriptor': 'PSU1,YSEF1600EM-2A01P10,S0A00A3032029000366,A00,3Y POWER,1600W',
                                            'status': 'OK',
                                            'value': 'Normal',
                                            'value_raw': None},
                                   'PSU2': {'descriptor': 'PSU2,YSEF1600EM-2A01P10,S0A00A3032029000366,A00,3Y POWER,1600W',
                                            'status': 'OK',
                                            'value': 'Normal',
                                            'value_raw': None}},
                  'Temperature Sensors': {'TempDrive1': {'descriptor': 'Temperature Sensor Drive 1',
                                                         'status': 'OK',
                                                         'value': '18.0 C',
                                                         'value_raw': None},
                                          'TempDrive10': {'descriptor': 'Temperature Sensor Drive 10',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive11': {'descriptor': 'Temperature Sensor Drive 11',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive12': {'descriptor': 'Temperature Sensor Drive 12',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive13': {'descriptor': 'Temperature Sensor Drive 13',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive14': {'descriptor': 'Temperature Sensor Drive 14',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive15': {'descriptor': 'Temperature Sensor Drive 15',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive16': {'descriptor': 'Temperature Sensor Drive 16',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive17': {'descriptor': 'Temperature Sensor Drive 17',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive18': {'descriptor': 'Temperature Sensor Drive 18',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive19': {'descriptor': 'Temperature Sensor Drive 19',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive2': {'descriptor': 'Temperature Sensor Drive 2',
                                                         'status': 'OK',
                                                         'value': '18.0 C',
                                                         'value_raw': None},
                                          'TempDrive20': {'descriptor': 'Temperature Sensor Drive 20',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive21': {'descriptor': 'Temperature Sensor Drive 21',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive22': {'descriptor': 'Temperature Sensor Drive 22',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive23': {'descriptor': 'Temperature Sensor Drive 23',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive24': {'descriptor': 'Temperature Sensor Drive 24',
                                                          'status': 'Not installed',
                                                          'value': None,
                                                          'value_raw': None},
                                          'TempDrive3': {'descriptor': 'Temperature Sensor Drive 3',
                                                         'status': 'OK',
                                                         'value': '17.0 C',
                                                         'value_raw': None},
                                          'TempDrive4': {'descriptor': 'Temperature Sensor Drive 4',
                                                         'status': 'Not installed',
                                                         'value': None,
                                                         'value_raw': None},
                                          'TempDrive5': {'descriptor': 'Temperature Sensor Drive 5',
                                                         'status': 'Not installed',
                                                         'value': None,
                                                         'value_raw': None},
                                          'TempDrive6': {'descriptor': 'Temperature Sensor Drive 6',
                                                         'status': 'Not installed',
                                                         'value': None,
                                                         'value_raw': None},
                                          'TempDrive7': {'descriptor': 'Temperature Sensor Drive 7',
                                                         'status': 'Not installed',
                                                         'value': None,
                                                         'value_raw': None},
                                          'TempDrive8': {'descriptor': 'Temperature Sensor Drive 8',
                                                         'status': 'Not installed',
                                                         'value': None,
                                                         'value_raw': None},
                                          'TempDrive9': {'descriptor': 'Temperature Sensor Drive 9',
                                                         'status': 'Not installed',
                                                         'value': None,
                                                         'value_raw': None},
                                          'TempPSU1Temp1': {'descriptor': 'TempPSU1Temp1',
                                                            'status': 'Not installed',
                                                            'value': None,
                                                            'value_raw': None},
                                          'TempPSU2Temp1': {'descriptor': 'TempPSU2Temp1',
                                                            'status': 'OK',
                                                            'value': '22.0 C',
                                                            'value_raw': None},
                                          'TempSensMidplane1': {'descriptor': 'Midplane Temp1',
                                                                'status': 'OK',
                                                                'value': '19.0 C',
                                                                'value_raw': None},
                                          'TempSensMidplane2': {'descriptor': 'Midplane Temp2',
                                                                'status': 'OK',
                                                                'value': '20.0 C',
                                                                'value_raw': None}},
                  'Voltage Sensor': {'VoltPS1Vin': {'descriptor': 'VoltPS1Vin',
                                                    'status': 'Not installed',
                                                    'value': None,
                                                    'value_raw': None},
                                     'VoltPS2Vin': {'descriptor': 'VoltPS2Vin',
                                                    'status': 'OK',
                                                    'value': '204.0',
                                                    'value_raw': None}}},
     'front_slots': 24,
     'id': uuid1,
     'internal_slots': 0,
     'model': 'ES24N',
     'name': 'ES24N JBoF Enclosure',
     'rackmount': True,
     'rear_slots': 0,
     'sg': None,
     'should_ignore': False,
     'status': ['OK'],
     'top_loaded': False}]


@pytest.mark.asyncio
async def test__jbof_redfish_comm_alert():
    m = Middleware()
    m['jbof.query'] = Mock(return_value=jbof_query_one)
    m['enclosure2.map_jbof'] = Mock(return_value=[])

    jas = JBOFAlertSource(m)
    alerts = await jas.check()
    assert len(alerts) == 1, alerts
    alert = alerts[0]
    assert alert == Alert(JBOFRedfishCommAlertClass, args=jbof1_id_dict)
    assert alert.formatted == f'JBOF: "{desc1}" ({ip1}/{ip2}) Failed to communicate with redfish interface.'


@pytest.mark.asyncio
async def test__jbof_no_alert():
    m = Middleware()
    m['jbof.query'] = Mock(return_value=jbof_query_one)
    m['enclosure2.map_jbof'] = Mock(return_value=jbof_data_one)

    jas = JBOFAlertSource(m)
    alerts = await jas.check()
    assert len(alerts) == 0, alerts


@pytest.mark.asyncio
async def test__jbof_invalid_data():
    data = copy.deepcopy(jbof_data_one)
    del data[0]['elements']
    m = Middleware()
    m['jbof.query'] = Mock(return_value=jbof_query_one)
    m['enclosure2.map_jbof'] = Mock(return_value=data)

    jas = JBOFAlertSource(m)
    alerts = await jas.check()
    assert len(alerts) == 1, alerts
    alert = alerts[0]
    assert alert.klass == JBOFInvalidDataAlertClass
    assert alert.formatted == f'JBOF: "{desc1}" ({ip1}/{ip2}) does not provide valid data for: elements'


@pytest.mark.asyncio
async def test__jbof_psu_critical():
    data = copy.deepcopy(jbof_data_one)
    data[0]['elements']['Power Supply']['PSU1'] = {
        'descriptor': 'PSU1,,,,',
        'status': 'Critical',
        'value': 'LossOfInput',
        'value_raw': None
    }
    m = Middleware()
    m['jbof.query'] = Mock(return_value=jbof_query_one)
    m['enclosure2.map_jbof'] = Mock(return_value=data)

    jas = JBOFAlertSource(m)
    alerts = await jas.check()
    assert len(alerts) == 1, alerts
    alert = alerts[0]
    assert alert.klass == JBOFElementCriticalAlertClass
    assert alert.formatted == f'JBOF: "{desc1}" ({ip1}/{ip2}) Power Supply PSU1 is critical: LossOfInput'


@pytest.mark.asyncio
async def test__jbof_fan_noncritical():
    data = copy.deepcopy(jbof_data_one)
    data[0]['elements']['Cooling']['Fan6'] = {
        'descriptor': 'Fan6',
        'status': 'Noncritical',
        'value': 'SpeedRPM=12345.0',
        'value_raw': None
    }
    m = Middleware()
    m['jbof.query'] = Mock(return_value=jbof_query_one)
    m['enclosure2.map_jbof'] = Mock(return_value=data)

    jas = JBOFAlertSource(m)
    alerts = await jas.check()
    assert len(alerts) == 1, alerts
    alert = alerts[0]
    assert alert.klass == JBOFElementWarningAlertClass
    assert alert.formatted == f'JBOF: "{desc1}" ({ip1}/{ip2}) Cooling Fan6 is noncritical: SpeedRPM=12345.0'


@pytest.mark.asyncio
async def test__jbof_temp_sensor_critical():
    data = copy.deepcopy(jbof_data_one)
    data[0]['elements']['Temperature Sensors']['TempDrive1'] = {
        'descriptor': 'Temperature Sensor Drive 1',
        'status': 'Critical',
        'value': '50.0 C',
        'value_raw': None
    }
    m = Middleware()
    m['jbof.query'] = Mock(return_value=jbof_query_one)
    m['enclosure2.map_jbof'] = Mock(return_value=data)

    jas = JBOFAlertSource(m)
    alerts = await jas.check()
    assert len(alerts) == 1, alerts
    alert = alerts[0]
    assert alert.klass == JBOFElementCriticalAlertClass
    assert alert.formatted == f'JBOF: "{desc1}" ({ip1}/{ip2}) Temperature Sensors TempDrive1 is critical: 50.0 C'


@pytest.mark.asyncio
async def test__jbof_volt_sensor_critical():
    data = copy.deepcopy(jbof_data_one)
    data[0]['elements']['Voltage Sensor']['VoltPS1Vin'] = {
        'descriptor': 'VoltPS1Vin',
        'status': 'Critical',
        'value': '100',
        'value_raw': None
    }
    m = Middleware()
    m['jbof.query'] = Mock(return_value=jbof_query_one)
    m['enclosure2.map_jbof'] = Mock(return_value=data)

    jas = JBOFAlertSource(m)
    alerts = await jas.check()
    assert len(alerts) == 1, alerts
    alert = alerts[0]
    assert alert.klass == JBOFElementCriticalAlertClass
    assert alert.formatted == f'JBOF: "{desc1}" ({ip1}/{ip2}) Voltage Sensor VoltPS1Vin is critical: 100'
