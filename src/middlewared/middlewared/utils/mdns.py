# NOTE: tests are provided in src/middlewared/middlewared/pytest/unit/utils/test_mdns.py
# Any updates to this file should have corresponding updates to tests

import enum
import socket
import xml.etree.ElementTree as xml

from io import StringIO
from typing import Any
from .filter_list import filter_list


AVAHI_SERVICE_PATH = '/etc/avahi/services'
SVC_HDR = '<?xml version="1.0" standalone="no"?><!DOCTYPE service-group SYSTEM "avahi-service.dtd">'
DISCARD = 9


class DevType(enum.Enum):
    AIRPORT = 'AirPort'
    APPLETV = 'AppleTv1,1'
    MACPRO = 'MacPro'
    MACPRORACK = 'MacPro7,1@ECOLOR=226,226,224'
    RACKMAC = 'RackMac'
    TIMECAPSULE = 'TimeCapsule6,106'
    XSERVE = 'Xserve'

    def __str__(self) -> str:
        return self.value


class ServiceType(enum.Enum):
    ADISK = ('_adisk._tcp.', DISCARD)
    DEV_INFO = ('_device-info._tcp.', DISCARD)
    HTTP = ('_http._tcp.', 80)
    SMB = ('_smb._tcp.', 445)
    NUT = ('_nut._tcp.', 3493)
    CUSTOM = (None, None)


class AvahiConst(enum.Enum):
    AVAHI_IF_UNSPEC = -1


def ip_addresses_to_interface_indexes(ifaces: list[dict[str, Any]], ip_addresses: list[str]) -> list[int]:
    """
    Avahi can bind services to particular physical intefaces using
    interface index. This is used to ensure that we don't adverise
    service availability on all networks.

    This particular method is used by the etc_files for services.

    `ifaces` - results of interface.query

    `ip_addresses` - list of ip_addresses the service is supposed
    to be bound to.
    """
    indexes: list[int] = []

    iface_filter: list[list[Any]] = [['OR', [
        ['state.aliases.*.address', 'in', ip_addresses],
        ['state.failover_virtual_aliases.*.address', 'in', ip_addresses]
    ]]]

    found = set([iface['id'] for iface in filter_list(ifaces, iface_filter)])
    for iface in found:
        indexes.append(socket.if_nametoindex(iface))

    return indexes


def parse_srv_record_data(data_in: str) -> list[dict[str, Any]]:
    """
    This function primarily exists for the purpose of CI tests.
    XML data for a service record is passed in as a string.

    Returns dictionary with basic information from data
    """
    output: list[dict[str, Any]] = []
    entry: dict[str, Any] | None = None
    with StringIO(data_in) as xmlbuf:
        root = xml.parse(xmlbuf).getroot()
        for elem in root.iter():
            match elem.tag:
                case 'service':
                    entry = {
                        'srv': None,
                        'port': None,
                        'interface': None,
                        'txt_records': []
                    }
                    output.append(entry)
                case 'type':
                    entry['srv'] = elem.text  # type: ignore
                case 'port':
                    entry['port'] = int(elem.text)  # type: ignore
                case 'interface':
                    entry['interface'] = int(elem.text)  # type: ignore
                case 'txt-record':
                    entry['txt_records'].append(elem.text)  # type: ignore
                case _:
                    pass

    return output


def generate_avahi_srv_record(
    service_type: str,
    interface_indexes: list[int] | None = None,
    txt_records: list[str] | None = None,
    custom_service_type: str | None = None,
    custom_port: int | None = None,
) -> str:
    """
    Generate XML string for service data for an avahi service. Takes
    the following parameters:

    `service_type`: See ServiceType enum above. If for some reason we are
    not generating one of our default record types in the enum and cannot
    expand it, then `CUSTOM` may be specified. In this case, the record
    type _must_ be specified via the kwarg `custom_sevice_type` and the
    port _must_ be specified via the kwarg `custom_port`. If port is
    indeterminate, then `9` (DISCARD protocol)  should be used.

    `interface_indexes`: list of interface indexes to which to bind this
    service. Should be left as None to advertise on all interfaces.
    NOTE: this will restrict advertisements beyond what is specified in
    global avahi configuration.

    `txt_records`: list of txt records to publish through the service
    entry.

    WARNING: avahi daemon sets an inotify watch on its services directory,
    the generate sevice record should be written to a path outside the
    directory and renamed over existing file.
    """
    svc_type = ServiceType[service_type]
    if svc_type == ServiceType.CUSTOM:
        if custom_service_type is None:
            raise ValueError('custom_service_type must be specifed')

        if custom_port is None:
            raise ValueError('custom_port must be specifed')

        srv = custom_service_type
        port = custom_port
    else:
        srv, port = svc_type.value

        if custom_port:
            port = custom_port

    txt_records = txt_records or []
    iface_indexes: list[int] | list[AvahiConst] = interface_indexes or [AvahiConst.AVAHI_IF_UNSPEC]  # type: ignore

    root = xml.Element("service-group")
    # We want to use replace-wildcards with %h here, rather than the hostname
    # because on hostname conflict:
    # 1. avahi will have to iterate thru names again
    # 2. avahi currently seems to generate a different postfix for host & service ('-23' vs ' #23')
    srv_name = xml.Element('name', {'replace-wildcards': 'yes'})
    srv_name.text = '%h'
    root.append(srv_name)

    for idx in iface_indexes:
        service = xml.Element('service')
        root.append(service)
        regtype = xml.SubElement(service, 'type')
        regtype.text = srv
        srvport = xml.SubElement(service, 'port')
        srvport.text = str(port)
        if idx != AvahiConst.AVAHI_IF_UNSPEC:
            iindex = xml.SubElement(service, 'interface')
            iindex.text = str(idx)

        for entry in txt_records:
            if not isinstance(entry, str):
                raise TypeError(f'{entry}: txt records must be string.')

            txt = xml.SubElement(service, 'txt-record')
            txt.text = entry

    xml_service_config = xml.ElementTree(root)
    with StringIO(SVC_HDR) as buf:
        xml_service_config.write(buf, 'unicode')
        buf.write('\n')
        buf.seek(0)
        record = buf.read()

    return record
