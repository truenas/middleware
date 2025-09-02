#!/usr/bin/env python3

"""
TrueNAS JBOF Visualizer

This script provides comprehensive visualization and analysis of JBOFs connected
to TrueNAS. It displays both textual and ASCII visual representations of JBOF
drive inventories, connectivity status, and ZFS pool mappings.

## Architecture Overview:

1. **Data Collection Layer** (Functions: get_jbof_info, gather_jbof_data, _collect_jbof_data_from_ip)
   - Queries TrueNAS API for JBOF configurations
   - Connects to JBOF management interfaces via Redfish API
   - Collects drive inventories, datapath interfaces, and connectivity status
   - Gathers TrueNAS NVMe devices, ZFS pools, and RDMA interface data

2. **Data Processing Layer** (Functions: map_*, analyze_*, get_primary_drives)
   - Maps management IPs to specific IOMs (Input/Output Modules)
   - Analyzes RDMA connectivity between TrueNAS and JBOF datapath interfaces
   - Correlates JBOF drive serial numbers with TrueNAS NVMe devices and ZFS pools
   - Generates drive state flags for mismatch detection between IOMs

3. **Data Structures** (Classes: JBOFConfiguration, JBOFSystem, *Result classes)
   - JBOFConfiguration: Raw JBOF config from TrueNAS API
   - JBOFSystem: Complete processed JBOF data with drives, connectivity, pool mappings
   - *Result classes: Structured results from API calls with status, details, and data

4. **Visualization Layer** (Functions: create_*, display_*)
   - Simple mode: Textual output with connectivity status, drive counts, pool assignments
   - Visual mode: ASCII diagrams showing side-by-side host and JBOF boxes with drive details
   - Dynamic column sizing based on actual data (device names, serial numbers, pool names)
   - Host positioning logic based on RDMA connectivity patterns

## Key Data Flow:
main() → gather_jbof_data() → display_*_with_data() → create_jbof_visualization() → create_*_box()

The script supports three modes: simple text output, ASCII visual diagrams, or both.
All data is collected once upfront to avoid redundant API calls between display modes.
"""

import argparse
import ipaddress
import json
import logging
import os
import requests
import subprocess
import urllib3
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from truenas_api_client import Client

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def setup_logging(level=logging.WARNING):
    """Setup logging configuration for the application."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )
    # Suppress noisy third-party library logs
    logging.getLogger('websocket').setLevel(level)


# Initialize logger
logger = logging.getLogger(__name__)


# Configuration Constants
class JBOFConfig:
    """Configuration constants for JBOF visualization and API interactions."""

    # Hardware constants
    STANDARD_SLOTS = 24

    # Timeout constants (seconds)
    DEFAULT_TIMEOUT = 10
    REDFISH_TIMEOUT = 5
    SUBPROCESS_TIMEOUT = 30

    # Display constants
    DEFAULT_JBOF_WIDTH = 52
    MAX_LINE_LENGTH = 120

    # Status constants
    DRIVE_ABSENT_STATES = ["absent", "empty", "missing"]
    CONNECTION_SUCCESS = "connected"
    LINK_UP_STATUS = "LinkUp"

    # API constants
    STATUS_SUCCESS = "success"
    STATUS_ERROR = "error"
    STATUS_TIMEOUT = "timeout"
    STATUS_NO_IP = "no_ip"
    STATUS_UUID_MISMATCH = "uuid_mismatch"

    # Ethernet port names
    ETHERNET_PORTS = ["Ethernet1", "Ethernet2"]
    IOM_NAMES = ["IOM1", "IOM2"]

    # HTTP Status codes
    HTTP_OK = 200
    HTTP_UNAUTHORIZED = 401
    HTTP_NOT_FOUND = 404

    # String truncation lengths
    UUID_DISPLAY_LENGTH = 8
    IP_DISPLAY_LENGTH = 15
    STATE_DISPLAY_LENGTH = 10

    # Layout constants
    HOST_MIN_WIDTH = 24
    BOX_BORDER_WIDTH = 2
    BOX_SPACING = 9
    SEPARATOR_COLUMNS = 4
    HEADER_ROOM = 8
    DRIVE_RANGE_START = 1
    DRIVE_RANGE_END = 25

    # Network defaults
    DEFAULT_PREFIX_LEN = 24
    RETURN_CODE_SUCCESS = 0

    # Column widths
    MIN_DEVICE_WIDTH = 8
    MIN_POOL_WIDTH = 4
    MIN_UUID_WIDTH = 5
    MIN_SERIAL_WIDTH = 13
    DRIVE_COL_WIDTH = 6
    IOM_STATE_WIDTH = 10

    # Separators
    SEPARATOR_25 = "=" * 25
    SEPARATOR_50 = "=" * 50
    SEPARATOR_80 = "=" * 80


# JBOF Data Structure Classes
@dataclass
class JBOFConfiguration:
    """JBOF configuration data from TrueNAS API jbof.query."""
    index: int
    description: str
    uuid: str
    mgmt_ip1: Optional[str] = None
    mgmt_ip2: Optional[str] = None
    mgmt_username: Optional[str] = None
    mgmt_password: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JBOFConfiguration':
        """Create JBOFConfiguration from raw dictionary data."""
        return cls(
            index=data.get('index', 0),
            description=data.get('description', ''),
            uuid=data.get('uuid', ''),
            mgmt_ip1=data.get('mgmt_ip1'),
            mgmt_ip2=data.get('mgmt_ip2'),
            mgmt_username=data.get('mgmt_username'),
            mgmt_password=data.get('mgmt_password')
        )


@dataclass
class ConnectivityResult:
    """Result of a connectivity check (Redfish, drive inventory, etc.)"""
    status: str
    details: str
    uuid: Optional[str] = None


@dataclass
class DriveInfo:
    """Individual drive information from JBOF inventory"""
    id: str
    serial: str
    status: str
    name: Optional[str] = None
    model: Optional[str] = None
    capacity_bytes: Optional[int] = None


@dataclass
class DriveInventoryResult:
    """Result of drive inventory collection from JBOF"""
    status: str
    details: str
    drives: List[DriveInfo]
    total_slots: int = 0
    present_drives: int = 0
    absent_drives: int = 0


@dataclass
class DatapathInterface:
    """Individual datapath network interface info"""
    status: str
    details: Optional[str] = None
    health: Optional[str] = None
    link_status: Optional[str] = None
    speed_mbps: Optional[int] = None
    mac_address: Optional[str] = None
    mtu: Optional[int] = None
    ip_addresses: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class DatapathInterfaceResult:
    """Result of datapath interface collection from JBOF"""
    status: str
    details: str
    interfaces: Dict[str, Dict[str, DatapathInterface]]


@dataclass
class IOMManagementInterface:
    """Result of IOM management interface query"""
    status: str
    details: str
    ip_address: Optional[str] = None
    all_ips: List[str] = field(default_factory=list)


@dataclass
class IOMInfo:
    """Information for a single IOM (I/O Module)"""
    mgmt_ip: Optional[str]
    status: str
    interface_ip: Optional[str] = None


@dataclass
class IOMMappingResult:
    """Result of mapping management IPs to IOMs"""
    status: str
    details: str
    mapping: Dict[str, IOMInfo]


@dataclass
class RDMAConnectivity:
    """Individual RDMA interface connectivity analysis"""
    node: str
    ifname: str
    address: str
    mtu: int
    is_current_node: bool
    status: str
    details: str
    jbof_connectivity: List[Dict[str, Any]]


@dataclass
class RDMAInterfaceResult:
    """Result of TrueNAS RDMA interface query"""
    status: str
    details: str
    interfaces: List[Dict[str, Any]]


@dataclass
class RDMAConnectivityResult:
    """Result of RDMA connectivity analysis"""
    status: str
    details: str
    connectivity: List[RDMAConnectivity]
    summary: Dict[str, int]


@dataclass
class PoolMapping:
    """Individual JBOF drive to ZFS pool mapping"""
    jbof_drive_id: str
    jbof_serial: str
    nvme_device: Optional[str] = None
    partuuid: Optional[str] = None
    pool_name: Optional[str] = None
    pool_status: Optional[str] = None
    vdev_type: Optional[str] = None
    status: str = "unknown"


@dataclass
class PoolMappingResult:
    """Result of JBOF drive to pool mapping analysis"""
    status: str
    details: str
    mappings: List[PoolMapping]
    summary: Dict[str, int]


@dataclass
class JBOFSystem:
    """Complete JBOF system information"""
    # Basic JBOF configuration
    name: str
    index: int
    uuid: str
    description: str
    # JBOF configuration data
    config: JBOFConfiguration

    # IOM management and connectivity
    iom1: IOMInfo
    iom2: IOMInfo
    iom_mapping: IOMMappingResult

    # Drive inventory from both IOMs
    drives1: List[DriveInfo]  # IOM1 drives
    drives2: List[DriveInfo]  # IOM2 drives

    # Network interfaces
    datapath_interfaces: Dict[str, Dict[str, DatapathInterface]]

    # RDMA connectivity analysis
    rdma_analysis: Optional[RDMAConnectivityResult]

    # Pool mappings
    pool_mapping: Optional[PoolMappingResult]


@dataclass
class NVMEDevice:
    """Individual NVMe device information"""
    device_path: str
    serial_number: str
    model_number: str
    namespace: str
    firmware: str = "Unknown"
    usage_bytes: Optional[int] = None
    physical_size: Optional[int] = None


@dataclass
class PartUUIDMapping:
    """Individual partition UUID mapping"""
    device: str
    base_device: str
    path: str


@dataclass
class NVMEDeviceResult:
    """Result of TrueNAS NVMe device query"""
    status: str
    details: str
    devices: List[NVMEDevice]


@dataclass
class PartUUIDMappingResult:
    """Result of partition UUID to NVMe device mapping"""
    status: str
    details: str
    mapping: Dict[str, PartUUIDMapping]


@dataclass
class ZFSPoolResult:
    """Result of ZFS pool query"""
    status: str
    details: str
    pools: List[Dict[str, Any]]  # ZFS pool structure is too complex, keep as dict for now


@dataclass
class TrueNASNodeInfoResult:
    """Result of TrueNAS node information query"""
    status: str
    details: str
    current_node: str
    is_ha: bool
    raw_node: str


@dataclass
class TrueNASSystemInfo:
    """TrueNAS system-wide information"""
    nvme_devices: NVMEDeviceResult
    partuuid_mappings: PartUUIDMappingResult
    zfs_pools: ZFSPoolResult
    node_info: TrueNASNodeInfoResult
    rdma_interfaces: RDMAInterfaceResult


@dataclass
class JBOFSystemData:
    """Top-level container for all JBOF system data"""
    truenas_info: TrueNASSystemInfo
    jbof_systems: List[JBOFSystem]


def create_request_error_result(exception, timeout=None, result_class=None, **kwargs):
    """Create standardized error results for request exceptions.

    Args:
        exception: The exception that occurred
        timeout: Timeout value for timeout errors
        result_class: Result class to instantiate (ConnectivityResult, etc.)
        **kwargs: Additional fields for the result class

    Returns:
        Error result instance or dict
    """
    if isinstance(exception, requests.exceptions.ConnectTimeout):
        status = "timeout"
        details = f"Connection timeout after {timeout or JBOFConfig.DEFAULT_TIMEOUT}s"
    elif isinstance(exception, requests.exceptions.ConnectionError):
        status = "unreachable"
        details = "Connection refused or host unreachable"
    else:
        status = "error"
        details = f"Error: {str(exception)}"

    if result_class:
        return result_class(status=status, details=details, **kwargs)
    else:
        return {"status": status, "details": details}


def get_primary_drives(drives1: List[DriveInfo], drives2: List[DriveInfo]) -> List[DriveInfo]:
    """Get primary drive list, preferring drives1 if available, falling back to drives2.

    Args:
        drives1: Drive inventory from IOM1
        drives2: Drive inventory from IOM2

    Returns:
        List of DriveInfo objects from the first available IOM
    """
    if drives1:
        return drives1
    elif drives2:
        return drives2
    else:
        return []


def get_jbof_info() -> List[JBOFConfiguration]:
    """Retrieve JBOF information from TrueNAS API.

    Returns:
        List of JBOFConfiguration objects containing management IPs,
        credentials, UUIDs, descriptions, and other JBOF settings.
        Returns empty list if no JBOFs configured or API call fails.
    """
    jbof_configs = []

    try:
        with Client() as c:
            for jbof_dict in c.call('jbof.query'):
                jbof_config = JBOFConfiguration.from_dict(jbof_dict)
                jbof_configs.append(jbof_config)
    except Exception as e:
        logger.error(f"Error connecting to TrueNAS API: {e}")
        return []

    return jbof_configs


def check_redfish_connectivity(ip_address: str, expected_uuid: Optional[str] = None,
                               timeout: int = JBOFConfig.REDFISH_TIMEOUT) -> ConnectivityResult:
    """Check connectivity to Redfish API endpoint and optionally validate UUID.

    Args:
        ip_address: IP address of the Redfish management interface
        expected_uuid: Optional UUID to validate against the discovered system UUID
        timeout: Connection timeout in seconds

    Returns:
        ConnectivityResult with connectivity status, details, and optional UUID
    """
    if not ip_address:
        return ConnectivityResult(status="no_ip", details="No IP address configured", uuid=None)

    url = f"https://{ip_address}/redfish/v1"

    try:
        response = requests.get(url, verify=False, timeout=timeout)
        if response.status_code == JBOFConfig.HTTP_OK:
            try:
                data = response.json()
                product = data.get("Product", "Unknown")
                redfish_version = data.get("RedfishVersion", "Unknown")
                redfish_uuid = data.get("UUID")

                # Build base details
                details = f"Product: {product}, Redfish: {redfish_version}"

                # Check UUID if provided
                if expected_uuid and redfish_uuid:
                    if redfish_uuid.lower() == expected_uuid.lower():
                        uuid_status = "UUID: ✓ Match"
                    else:
                        uuid_status = f"UUID: ✗ Mismatch (Got: {redfish_uuid[:JBOFConfig.UUID_DISPLAY_LENGTH]}...)"
                    details += f", {uuid_status}"
                elif redfish_uuid:
                    details += f", UUID: {redfish_uuid[:JBOFConfig.UUID_DISPLAY_LENGTH]}..."
                return ConnectivityResult(
                    status=JBOFConfig.CONNECTION_SUCCESS,
                    details=details,
                    uuid=redfish_uuid
                )
            except json.JSONDecodeError:
                return ConnectivityResult(
                    status=JBOFConfig.CONNECTION_SUCCESS,
                    details="Connected but invalid JSON response",
                    uuid=None
                )
        else:
            return ConnectivityResult(status="error", details=f"HTTP {response.status_code}", uuid=None)
    except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError, Exception) as e:
        return create_request_error_result(e, timeout, ConnectivityResult, uuid=None)


def get_drive_inventory(ip_address: str, username: str, password: str,
                        timeout: int = JBOFConfig.DEFAULT_TIMEOUT) -> DriveInventoryResult:
    """Get drive inventory from Redfish API.

    Args:
        ip_address: IP address of the Redfish management interface
        username: Authentication username
        password: Authentication password
        timeout: Request timeout in seconds

    Returns:
        DriveInventoryResult containing:
        - status: Connection/operation status
        - details: Human-readable status description
        - drives: List of DriveInfo objects (if successful)
        - total_slots: Total number of drive slots
        - present_drives: Number of drives currently present
        - absent_drives: Number of empty/absent drive slots
    """
    if not ip_address:
        return DriveInventoryResult(status="no_ip", details="No IP address configured", drives=[])

    url = f"https://{ip_address}/redfish/v1/Chassis/2U24/Drives/?$expand=*"

    try:
        response = requests.get(url, auth=(username, password), verify=False, timeout=timeout)
        if response.status_code == JBOFConfig.HTTP_OK:
            try:
                data = response.json()
                drives = []

                # Extract drive information
                members = data.get("Members", [])
                for drive in members:
                    drive_status = drive.get("Status", {}).get("State", "Unknown")
                    # Only include drives that are actually present (not absent/empty slots)
                    if drive_status.lower() not in JBOFConfig.DRIVE_ABSENT_STATES:
                        drive_info = DriveInfo(
                            id=drive.get("Id", "Unknown"),
                            name=drive.get("Name", "Unknown"),
                            serial=drive.get("SerialNumber", "Unknown"),
                            model=drive.get("Model", "Unknown"),
                            capacity_bytes=drive.get("CapacityBytes"),
                            status=drive_status
                        )
                        drives.append(drive_info)

                # Count total slots and present drives
                total_slots = len(members)
                present_drives = len(drives)
                absent_drives = total_slots - present_drives

                details = f"Found {present_drives} drives present"
                if absent_drives > 0:
                    details += f" ({absent_drives} slots empty/absent)"
                return DriveInventoryResult(
                    status=JBOFConfig.STATUS_SUCCESS,
                    details=details,
                    drives=drives,
                    total_slots=total_slots,
                    present_drives=present_drives,
                    absent_drives=absent_drives
                )
            except (json.JSONDecodeError, KeyError) as e:
                return DriveInventoryResult(status="parse_error", details=f"JSON parse error: {str(e)}", drives=[])
        elif response.status_code == JBOFConfig.HTTP_UNAUTHORIZED:
            return DriveInventoryResult(status="auth_error", details="Authentication failed", drives=[])
        elif response.status_code == JBOFConfig.HTTP_NOT_FOUND:
            return DriveInventoryResult(status="not_found", details="Drive endpoint not found", drives=[])
        else:
            return DriveInventoryResult(status="http_error", details=f"HTTP {response.status_code}", drives=[])
    except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError, Exception) as e:
        return create_request_error_result(e, timeout, DriveInventoryResult, drives=[])


def get_datapath_interfaces(ip_address: str, username: str, password: str,
                            timeout: int = 10) -> DatapathInterfaceResult:
    """Get datapath network interface information from both IOMs via Redfish API.

    Args:
        ip_address: IP address of the Redfish management interface
        username: Authentication username
        password: Authentication password
        timeout: Request timeout in seconds

    Returns:
        DatapathInterfaceResult containing:
        - status: Operation status
        - details: Human-readable status description
        - interfaces: Dict mapping IOM names to their ethernet interface data
    """
    if not ip_address:
        return DatapathInterfaceResult(status="no_ip", details="No IP address configured", interfaces={})

    interfaces = {}

    # Check both IOMs and their Ethernet interfaces
    iom_configs = [
        ("IOM1", JBOFConfig.ETHERNET_PORTS),
        ("IOM2", JBOFConfig.ETHERNET_PORTS)
    ]

    for iom_name, ethernet_ports in iom_configs:
        interfaces[iom_name] = {}

        for eth_port in ethernet_ports:
            url = (f"https://{ip_address}/redfish/v1/Chassis/{iom_name}/NetworkAdapters/1/"
                   f"NetworkDeviceFunctions/{eth_port}/EthernetInterfaces/1")

            try:
                response = requests.get(url, auth=(username, password), verify=False, timeout=timeout)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        # Extract IP addresses if available
                        ip_addresses = []
                        ipv4_addresses = data.get("IPv4Addresses", [])
                        for ip_info in ipv4_addresses:
                            if ip_info.get("Address"):
                                ip_addresses.append({
                                    "address": ip_info.get("Address"),
                                    "subnet_mask": ip_info.get("SubnetMask"),
                                    "address_origin": ip_info.get("AddressOrigin")
                                })

                        interfaces[iom_name][eth_port] = DatapathInterface(
                            status=JBOFConfig.STATUS_SUCCESS,
                            health=data.get("Status", {}).get("Health", "Unknown"),
                            link_status=data.get("LinkStatus", "Unknown"),
                            speed_mbps=data.get("SpeedMbps"),
                            mac_address=data.get("MACAddress"),
                            mtu=data.get("MTUSize"),
                            ip_addresses=ip_addresses
                        )
                    except (json.JSONDecodeError, KeyError) as e:
                        interfaces[iom_name][eth_port] = DatapathInterface(
                            status="parse_error",
                            details=f"JSON parse error: {str(e)}"
                        )
                elif response.status_code == 404:
                    interfaces[iom_name][eth_port] = DatapathInterface(
                        status="not_found",
                        details="Interface not found"
                    )
                elif response.status_code == 401:
                    interfaces[iom_name][eth_port] = DatapathInterface(
                        status="auth_error",
                        details="Authentication failed"
                    )
                else:
                    interfaces[iom_name][eth_port] = DatapathInterface(
                        status="http_error",
                        details=f"HTTP {response.status_code}"
                    )
            except requests.exceptions.ConnectTimeout:
                interfaces[iom_name][eth_port] = DatapathInterface(
                    status="timeout",
                    details=f"Connection timeout after {timeout}s"
                )
            except requests.exceptions.ConnectionError:
                interfaces[iom_name][eth_port] = DatapathInterface(
                    status="unreachable",
                    details="Connection refused or host unreachable"
                )
            except Exception as e:
                interfaces[iom_name][eth_port] = DatapathInterface(
                    status="error",
                    details=f"Error: {str(e)}"
                )

    return DatapathInterfaceResult(status="success", details="Datapath interface check completed",
                                   interfaces=interfaces)


def get_iom_management_interface(ip_address: str, username: str, password: str,
                                 iom_name: str, timeout: int = JBOFConfig.REDFISH_TIMEOUT) -> IOMManagementInterface:
    """Get management interface information for a specific IOM via Redfish API.

    Args:
        ip_address: IP address of the Redfish management interface
        username: Authentication username
        password: Authentication password
        iom_name: Name of the IOM to query (e.g., "IOM1", "IOM2")
        timeout: Request timeout in seconds

    Returns:
        IOMManagementInterface containing:
        - status: Operation status
        - details: Human-readable status description
        - ip_address: Management IP address if found
    """
    if not ip_address:
        return IOMManagementInterface(status="no_ip", details="No IP address configured")

    url = f"https://{ip_address}/redfish/v1/Managers/{iom_name}/EthernetInterfaces/1"

    try:
        response = requests.get(url, auth=(username, password), verify=False, timeout=timeout)
        if response.status_code == 200:
            try:
                data = response.json()

                # Extract IP addresses
                ip_addresses = []
                for ipv4 in data.get("IPv4Addresses", []):
                    if ipv4.get("Address"):
                        ip_addresses.append(ipv4["Address"])

                return IOMManagementInterface(
                    status=JBOFConfig.STATUS_SUCCESS,
                    details=f"Management IP: {ip_addresses[0] if ip_addresses else 'None'}",
                    ip_address=ip_addresses[0] if ip_addresses else None,
                    all_ips=ip_addresses
                )
            except json.JSONDecodeError:
                return IOMManagementInterface(status="parse_error", details="JSON parse error")
        elif response.status_code == 404:
            return IOMManagementInterface(status="not_found", details="IOM management interface not found")
        elif response.status_code == 401:
            return IOMManagementInterface(status="auth_error", details="Authentication failed")
        else:
            return IOMManagementInterface(status="http_error", details=f"HTTP {response.status_code}")
    except requests.exceptions.ConnectTimeout:
        return IOMManagementInterface(status="timeout", details=f"Connection timeout after {timeout}s")
    except requests.exceptions.ConnectionError:
        return IOMManagementInterface(status="unreachable", details="Connection refused or host unreachable")
    except Exception as e:
        return IOMManagementInterface(status="error", details=f"Error: {str(e)}")


def map_management_ips_to_ioms(jbof_config: JBOFConfiguration) -> IOMMappingResult:
    """Map management IPs to their corresponding IOMs by testing connectivity.

    Args:
        jbof_config: JBOF configuration containing management IPs and credentials

    Returns:
        IOMMappingResult containing:
        - status: Overall mapping operation status
        - details: Human-readable summary of mapping results
        - mapping: Dict mapping IOM names to IOMInfo objects with connection details
    """
    # Initialize mapping with unknown status for all IOMs
    iom_mapping = {iom_name: IOMInfo(mgmt_ip=None, status="unknown")
                   for iom_name in JBOFConfig.IOM_NAMES}

    # Early return if no credentials
    if not jbof_config.mgmt_username or not jbof_config.mgmt_password:
        return IOMMappingResult(
            status="no_credentials",
            details="No management credentials available",
            mapping=iom_mapping
        )

    # Test each management IP against each IOM
    for mgmt_ip in [jbof_config.mgmt_ip1, jbof_config.mgmt_ip2]:
        if not mgmt_ip:  # Skip None/empty IPs
            continue

        for iom_name in JBOFConfig.IOM_NAMES:
            result = get_iom_management_interface(mgmt_ip, jbof_config.mgmt_username,
                                                  jbof_config.mgmt_password, iom_name)
            if result.status == JBOFConfig.STATUS_SUCCESS:
                iom_mapping[iom_name] = IOMInfo(
                    mgmt_ip=mgmt_ip,
                    status="connected",
                    interface_ip=result.ip_address
                )

    # Generate summary
    connected_count = sum(1 for info in iom_mapping.values() if info.status == "connected")
    details = f"Mapped {connected_count} management IPs to IOMs"

    return IOMMappingResult(
        status=JBOFConfig.STATUS_SUCCESS,
        details=details,
        mapping=iom_mapping
    )


def get_truenas_nvme_devices() -> NVMEDeviceResult:
    """Get NVMe device list from TrueNAS using nvme list command.

    Returns:
        NVMEDeviceResult containing:
        - status: Command execution status
        - details: Human-readable status description
        - devices: List of NVMe device information dictionaries (if successful)
        - summary: Summary with total device count and visibility info
    """
    try:
        result = subprocess.run(['nvme', 'list', '-o', 'json'],
                                capture_output=True, text=True, timeout=JBOFConfig.SUBPROCESS_TIMEOUT)

        if result.returncode == JBOFConfig.RETURN_CODE_SUCCESS:
            try:
                nvme_data = json.loads(result.stdout)
                devices = []

                # Extract device information from nvme list output
                for device in nvme_data.get("Devices", []):
                    device_info = NVMEDevice(
                        device_path=device.get("DevicePath", "Unknown"),
                        serial_number=device.get("SerialNumber", "Unknown").strip(),
                        model_number=device.get("ModelNumber", "Unknown").strip(),
                        namespace=device.get("Namespace", "Unknown"),
                        firmware=device.get("Firmware", "Unknown"),
                        usage_bytes=device.get("UsedBytes"),
                        physical_size=device.get("PhysicalSize")
                    )
                    devices.append(device_info)

                return NVMEDeviceResult(
                    status=JBOFConfig.STATUS_SUCCESS,
                    devices=devices,
                    details=f"Found {len(devices)} NVMe devices on TrueNAS"
                )
            except json.JSONDecodeError as e:
                return NVMEDeviceResult(
                    status="parse_error",
                    devices=[],
                    details=f"Failed to parse nvme list JSON: {str(e)}"
                )
        else:
            return NVMEDeviceResult(
                status="command_error",
                devices=[],
                details=f"nvme list command failed: {result.stderr.strip() or 'Unknown error'}"
            )
    except subprocess.TimeoutExpired:
        return NVMEDeviceResult(
            status="timeout",
            devices=[],
            details="nvme list command timed out after 30 seconds"
        )
    except FileNotFoundError:
        return NVMEDeviceResult(
            status="not_available",
            devices=[],
            details="nvme command not found on system"
        )
    except Exception as e:
        return NVMEDeviceResult(
            status="error",
            devices=[],
            details=f"Error running nvme list: {str(e)}"
        )


def get_partuuid_to_nvme_mapping() -> PartUUIDMappingResult:
    """Get mapping from partuuid to nvme device by examining /dev/disk/by-partuuid/."""
    partuuid_mapping = {}
    partuuid_dir = "/dev/disk/by-partuuid"

    try:
        if not os.path.exists(partuuid_dir):
            return PartUUIDMappingResult(status="not_found", mapping={}, details="by-partuuid directory not found")

        for partuuid in os.listdir(partuuid_dir):
            try:
                link_path = os.path.join(partuuid_dir, partuuid)
                target = os.readlink(link_path)
                # Extract device name from target (e.g., "../../nvme15n1p1" -> "nvme15n1p1")
                device_name = os.path.basename(target)

                # Extract base nvme device (e.g., "nvme15n1p1" -> "nvme15n1")
                if device_name.startswith("nvme") and "n1p" in device_name:
                    base_device = device_name.split("p")[0]  # "nvme15n1p1" -> "nvme15n1"
                    partuuid_mapping[partuuid] = PartUUIDMapping(
                        device=device_name,
                        base_device=base_device,
                        path=target
                    )
            except (OSError, IndexError):
                continue

        return PartUUIDMappingResult(
            status=JBOFConfig.STATUS_SUCCESS,
            mapping=partuuid_mapping,
            details=f"Found {len(partuuid_mapping)} partuuid mappings"
        )
    except Exception as e:
        return PartUUIDMappingResult(
            status="error",
            mapping={},
            details=f"Error reading partuuid directory: {str(e)}"
        )


def get_zfs_pools() -> ZFSPoolResult:
    """Get ZFS pool information from TrueNAS API.

    Returns:
        ZFSPoolResult containing:
        - status: API call status
        - details: Human-readable status description
        - pools: List of ZFS pool data dictionaries (if successful)
    """
    try:
        with Client() as c:
            pools = c.call('pool.query')
            return ZFSPoolResult(
                status=JBOFConfig.STATUS_SUCCESS,
                pools=pools,
                details=f"Found {len(pools)} ZFS pools"
            )
    except Exception as e:
        return ZFSPoolResult(
            status="error",
            pools=[],
            details=f"Error querying pools: {str(e)}"
        )


def get_truenas_node_info() -> TrueNASNodeInfoResult:
    """Get TrueNAS node information (HA status)."""
    try:
        with Client() as c:
            node = c.call('failover.node')
            is_ha = node in ['A', 'B']
            # Treat MANUAL as standalone (same as 'A' for interface purposes)
            current_node = node if node in ['A', 'B'] else 'A'

            return TrueNASNodeInfoResult(
                status=JBOFConfig.STATUS_SUCCESS,
                current_node=current_node,
                is_ha=is_ha,
                raw_node=node,
                details=f"Node: {node}" + (" (HA pair)" if is_ha else " (standalone)")
            )
    except Exception as e:
        return TrueNASNodeInfoResult(
            status="error",
            current_node="A",
            is_ha=False,
            raw_node="Unknown",
            details=f"Error getting node info: {str(e)}"
        )


def get_truenas_rdma_interfaces() -> RDMAInterfaceResult:
    """Get TrueNAS RDMA interface configuration."""
    try:
        with Client() as c:
            rdma_interfaces = c.call('rdma.interface.query')

            return RDMAInterfaceResult(
                status=JBOFConfig.STATUS_SUCCESS,
                interfaces=rdma_interfaces,
                details=f"Found {len(rdma_interfaces)} RDMA interfaces configured"
            )
    except Exception as e:
        return RDMAInterfaceResult(
            status="error",
            interfaces=[],
            details=f"Error querying RDMA interfaces: {str(e)}"
        )


def analyze_rdma_connectivity(rdma_interfaces: RDMAInterfaceResult, node_info: TrueNASNodeInfoResult,
                              jbof_datapath_interfaces: Dict[str, Dict[str, DatapathInterface]]
                              ) -> RDMAConnectivityResult:
    """Analyze RDMA connectivity between TrueNAS and JBOF.

    Args:
        rdma_interfaces: RDMA interface configuration from TrueNAS API
        node_info: TrueNAS HA node information and current node status
        jbof_datapath_interfaces: JBOF datapath network interface data

    Returns:
        RDMAConnectivityResult containing:
        - status: Overall connectivity status
        - details: Human-readable connectivity summary
        - connectivity: List of RDMAConnectivityInfo objects for each interface
        - summary: Summary with total/active interface counts and connected JBOFs
    """
    if not rdma_interfaces.interfaces:
        return RDMAConnectivityResult(
            status="no_rdma_config",
            details="No RDMA interfaces configured on TrueNAS",
            connectivity=[],
            summary={"total_interfaces": 0, "active_interfaces": 0, "connected_jbofs": 0}
        )

    current_node = node_info.current_node
    is_ha = node_info.is_ha

    connectivity_analysis = []

    # Get JBOF IP addresses from datapath interfaces
    jbof_ips = set()
    for iom_name, iom_interfaces in jbof_datapath_interfaces.items():
        for eth_name, eth_info in iom_interfaces.items():
            if eth_info.status == JBOFConfig.STATUS_SUCCESS:
                for ip_info in eth_info.ip_addresses:
                    if ip_info.get("address"):
                        jbof_ips.add(ip_info["address"])

    # Analyze each RDMA interface
    for rdma_if in rdma_interfaces.interfaces:
        interface_node = rdma_if.get("node", "A")
        ifname = rdma_if.get("ifname", "Unknown")
        address = rdma_if.get("address", "Unknown")
        mtu = rdma_if.get("mtu", 0)

        # Check if this interface is on the current node
        if interface_node == current_node:
            status = "active"
            details = f"Active on current node ({current_node})"
        elif is_ha:
            status = "standby"
            details = f"Standby on HA peer node ({interface_node})"
        else:
            status = "inactive"
            details = "Not on current node"

        # Check potential connectivity to JBOF IPs (basic subnet analysis)
        jbof_connectivity = []
        for jbof_ip in jbof_ips:
            if _are_in_same_subnet(address, jbof_ip, rdma_if.get("prefixlen", JBOFConfig.DEFAULT_PREFIX_LEN)):
                jbof_connectivity.append({
                    "jbof_ip": jbof_ip,
                    "subnet_match": True,
                    "details": f"Same subnet as JBOF {jbof_ip}"
                })

        analysis = RDMAConnectivity(
            node=interface_node,
            ifname=ifname,
            address=address,
            mtu=mtu,
            is_current_node=interface_node == current_node,
            status=status,
            details=details,
            jbof_connectivity=jbof_connectivity
        )

        connectivity_analysis.append(analysis)

    # Generate summary
    active_interfaces = [a for a in connectivity_analysis if a.status == "active"]
    connected_jbofs = sum(len(a.jbof_connectivity) for a in active_interfaces)

    if active_interfaces:
        details = f"✓ {len(active_interfaces)} active RDMA interfaces"
        if connected_jbofs > 0:
            details += f", potential connectivity to {connected_jbofs} JBOF IPs"
        else:
            details += ", no subnet matches with JBOF IPs"
    else:
        details = "✗ No active RDMA interfaces on current node"

    return RDMAConnectivityResult(
        status="analyzed",
        details=details,
        connectivity=connectivity_analysis,
        summary={
            "total_interfaces": len(connectivity_analysis),
            "active_interfaces": len(active_interfaces),
            "connected_jbofs": connected_jbofs
        }
    )


def _are_in_same_subnet(ip1: str, ip2: str, prefix_len: int) -> bool:
    """Check if two IP addresses are in the same subnet.

    Args:
        ip1: First IP address
        ip2: Second IP address
        prefix_len: Subnet prefix length (e.g., 24 for /24)

    Returns:
        True if both IPs are in the same subnet, False otherwise
    """
    try:
        network = ipaddress.ip_network(f"{ip1}/{prefix_len}", strict=False)
        return ipaddress.ip_address(ip2) in network
    except Exception:
        # Fallback: simple string comparison for basic cases
        return ip1.rsplit('.', 1)[0] == ip2.rsplit('.', 1)[0]


def determine_host_position(rdma_analysis: RDMAConnectivityResult,
                            datapath_interfaces: Dict[str, Dict[str, DatapathInterface]]) -> str:
    """Determine whether host box should be on left or right based on RDMA connectivity."""
    # Default to left for Node A/MANUAL
    position = "left"

    if not rdma_analysis or not rdma_analysis.connectivity:
        return position

    # Get active RDMA interfaces
    active_rdma = [c for c in rdma_analysis.connectivity if c.status == "active"]
    if not active_rdma:
        return position

    # Count connections to each IOM
    iom1_connections = 0
    iom2_connections = 0

    for rdma_interface in active_rdma:
        for conn in rdma_interface.jbof_connectivity:
            jbof_ip = conn["jbof_ip"]

            # Check which IOM this IP belongs to
            for iom in JBOFConfig.IOM_NAMES:
                for eth_port in JBOFConfig.ETHERNET_PORTS:
                    if (iom in datapath_interfaces and
                            eth_port in datapath_interfaces[iom] and
                            datapath_interfaces[iom][eth_port].status == JBOFConfig.STATUS_SUCCESS):

                        interface = datapath_interfaces[iom][eth_port]
                        for ip_info in interface.ip_addresses:
                            if ip_info.get("address") == jbof_ip:
                                if iom == "IOM1":
                                    iom1_connections += 1
                                else:
                                    iom2_connections += 1

    # If more connections to IOM2, position host on right
    if iom2_connections > iom1_connections:
        position = "right"

    return position


def get_drive_state_flags(drives1: List[DriveInfo], drives2: List[DriveInfo]) -> Dict[str, str]:
    """Generate state mismatch flags for drive table based on IOM1/IOM2 state differences.

    Args:
        drives1: Drive inventory from IOM1
        drives2: Drive inventory from IOM2

    Returns:
        Dict mapping drive IDs to flag characters indicating state mismatches
    """
    flags = {}

    # Create state mappings by drive ID
    states1 = {drive.id: drive.status for drive in drives1}
    states2 = {drive.id: drive.status for drive in drives2}

    # Get all drive IDs
    all_drive_ids = set(states1.keys()) | set(states2.keys())

    for drive_id in all_drive_ids:
        state1 = states1.get(drive_id, "Missing")
        state2 = states2.get(drive_id, "Missing")

        # Determine flag based on states
        if state1 == "Unknown" or state2 == "Unknown":
            flags[drive_id] = "?"
        elif state1 == "Missing" or state2 == "Missing":
            flags[drive_id] = "X"
        elif state1.lower() in ["failed", "error"] or state2.lower() in ["failed", "error"]:
            flags[drive_id] = "X"
        elif state1 != state2:
            flags[drive_id] = "!"
        else:
            flags[drive_id] = " "

    return flags


def _map_rdma_to_datapath(rdma_analysis, datapath_interfaces):
    """Map RDMA interfaces to their corresponding datapath interfaces (DP1/DP2)."""
    mapping = {}

    if not rdma_analysis or not rdma_analysis.connectivity:
        return mapping

    active_interfaces = [c for c in rdma_analysis.connectivity if c.status == "active"]

    for rdma_interface in active_interfaces:
        rdma_name = rdma_interface.ifname
        rdma_ip = rdma_interface.address
        rdma_display = f"{rdma_name}: {rdma_ip}"

        for conn in rdma_interface.jbof_connectivity:
            jbof_ip = conn["jbof_ip"]

            # Check which datapath interface this IP belongs to
            for iom in JBOFConfig.IOM_NAMES:
                iom_interfaces = datapath_interfaces.get(iom, {})

                # Check DP1 (Ethernet1)
                if ("Ethernet1" in iom_interfaces and
                        iom_interfaces["Ethernet1"].status == JBOFConfig.STATUS_SUCCESS):
                    interface = iom_interfaces["Ethernet1"]
                    for ip_info in interface.ip_addresses:
                        if ip_info.get("address") == jbof_ip:
                            if "DP1" not in mapping:  # Only map first matching RDMA
                                mapping["DP1"] = rdma_display

                # Check DP2 (Ethernet2)
                if ("Ethernet2" in iom_interfaces and
                        iom_interfaces["Ethernet2"].status == JBOFConfig.STATUS_SUCCESS):
                    interface = iom_interfaces["Ethernet2"]
                    for ip_info in interface.ip_addresses:
                        if ip_info.get("address") == jbof_ip:
                            if "DP2" not in mapping:  # Only map first matching RDMA
                                mapping["DP2"] = rdma_display

    return mapping


def create_host_box(pool_mapping: PoolMappingResult, rdma_analysis: RDMAConnectivityResult,
                    node_info: Optional[TrueNASNodeInfoResult],
                    datapath_interfaces: Dict[str, Dict[str, DatapathInterface]],
                    box_height: int, col_widths: Dict[str, int], drives1: List[DriveInfo],
                    drives2: List[DriveInfo]) -> List[str]:
    """Create the host information box."""
    lines = []
    current_node = node_info.current_node if node_info else "A"

    # Calculate dynamic host box width based on column widths
    table_width = col_widths["device"] + col_widths["pool"] + col_widths["uuid"] + 4  # +4 for separators
    host_width = max(JBOFConfig.HOST_MIN_WIDTH, table_width + JBOFConfig.BOX_BORDER_WIDTH)

    def pad_host_line(content):
        """Ensure host line is exactly the correct width."""
        if content.startswith("+") and content.endswith("+"):
            # Border line
            return content[:host_width]
        elif content.startswith("|") and content.endswith("|"):
            # Content line - pad to exact width
            inner_content = content[1:-1]  # Remove | characters
            padded_inner = inner_content[:host_width - 2].ljust(host_width - 2)
            return "|" + padded_inner + "|"
        else:
            return content[:host_width].ljust(host_width)

    # Header
    lines.append(pad_host_line("[Host-Node {}]".format(current_node)))
    lines.append(pad_host_line("+" + "-" * (host_width - 2) + "+"))

    # Create exactly 3 lines to match JBOF datapath section
    # Determine which datapath interface each RDMA connects to
    rdma_to_dp_mapping = _map_rdma_to_datapath(rdma_analysis, datapath_interfaces)

    # Line 1: Management info (matching JBOF mgmt line)
    lines.append(pad_host_line(f"| Node: {current_node:<16} |"))

    # Line 2: DP1-aligned RDMA (matching JBOF DP1 line)
    dp1_rdma = rdma_to_dp_mapping.get("DP1", "")
    if dp1_rdma:
        lines.append(pad_host_line(f"| {dp1_rdma:<20} |"))
    else:
        lines.append(pad_host_line(f"| {'(no DP1 connection)':<20} |"))

    # Line 3: DP2-aligned RDMA (matching JBOF DP2 line)
    dp2_rdma = rdma_to_dp_mapping.get("DP2", "")
    if dp2_rdma:
        lines.append(pad_host_line(f"| {dp2_rdma:<20} |"))
    else:
        lines.append(pad_host_line(f"| {'(no DP2 connection)':<20} |"))

    # Separator
    lines.append(pad_host_line("+" + "-" * (host_width - 2) + "+"))

    # Table header with dynamic widths - ensure separator matches header exactly
    header_line = (f"| {'Device':<{col_widths['device']}} |"
                   f"{'Pool':<{col_widths['pool']}}|"
                   f"{'UUID':<{col_widths['uuid']}} |")
    # Create separator by replacing all non-pipe characters with dashes
    separator_line = ''.join('-' if c != '|' else '|' for c in header_line)
    lines.append(pad_host_line(header_line))
    lines.append(pad_host_line(separator_line))

    # Drive mappings - correlate with JBOF drive slots
    # Create combined drive state map
    jbof_drives = {}
    for drive in drives1 + drives2:
        drive_id = drive.id
        if drive_id not in jbof_drives:  # Take first occurrence
            jbof_drives[drive_id] = drive.status

    for i in range(JBOFConfig.STANDARD_SLOTS):
        if i >= box_height - JBOFConfig.HEADER_ROOM:
            break

        drive_slot = str(i + JBOFConfig.DRIVE_RANGE_START)
        jbof_drive_status = jbof_drives.get(drive_slot, "Absent")

        # If JBOF drive is absent/empty/missing, show empty host entry
        if jbof_drive_status.lower() in JBOFConfig.DRIVE_ABSENT_STATES:
            device = "(empty)"
            pool = ""
            uuid = ""
        else:
            # Find the mapping for this JBOF drive slot by matching drive ID
            mapping = None
            if pool_mapping and pool_mapping.mappings:
                for m in pool_mapping.mappings:
                    if str(m.jbof_drive_id) == drive_slot:
                        mapping = m
                        break

            if mapping:
                device = mapping.nvme_device or "(not_seen)"
                pool = mapping.pool_name or ""
                uuid = mapping.partuuid or ""

                # Handle specific mapping statuses
                if mapping.status == "nvme_not_found":
                    device = "(not_seen)"
                elif mapping.status == "no_pool":
                    device = device if device != "(not_seen)" else "nvmeXnX"
                    pool = ""
                    # Keep the UUID for drives not in pools
                elif not device or device == "None":
                    device = "(empty)"
                    pool = ""
                    uuid = ""
            else:
                device = "(not_seen)"
                pool = ""
                uuid = ""

        # Use dynamic column widths - no truncation
        line = f"| {device:<{col_widths['device']}} |{pool:<{col_widths['pool']}}|{uuid:<{col_widths['uuid']}} |"
        lines.append(pad_host_line(line))

    # Fill remaining lines to match box height
    while len(lines) < box_height - 1:  # -1 because footer will be added
        lines.append(pad_host_line("|" + " " * (host_width - 2) + "|"))

    # Footer
    lines.append(pad_host_line("+" + "-" * (host_width - 2) + "+"))

    return lines


def create_jbof_box(jbof_config: JBOFConfiguration, drives1: List[DriveInfo], drives2: List[DriveInfo],
                    datapath_interfaces: Dict[str, Dict[str, DatapathInterface]], iom_mapping: IOMMappingResult,
                    col_widths: Dict[str, int]) -> List[str]:
    """Create the central JBOF information box."""
    lines = []

    # Calculate dynamic JBOF box width based on serial number column
    # Drive table: | Drive | IOM1 State | Serial_Number | IOM2 State | Flag |
    drive_table_width = 6 + 1 + 12 + 1 + col_widths["serial"] + 1 + 12 + 1 + 1 + 1  # +separators
    header_min_width = JBOFConfig.DEFAULT_JBOF_WIDTH  # Minimum for header content
    jbof_width = max(header_min_width, drive_table_width)

    def pad_jbof_line(content):
        """Ensure JBOF line is exactly the correct width."""
        if content.startswith("+") and content.endswith("+"):
            # Border line
            return content[:jbof_width]
        elif content.startswith("|") and content.endswith("|"):
            # Content line - pad to exact width
            inner_content = content[1:-1]  # Remove | characters
            padded_inner = inner_content[:jbof_width - 2].ljust(jbof_width - 2)
            return "|" + padded_inner + "|"
        else:
            return content[:jbof_width].ljust(jbof_width)

    # Header
    jbof_desc = jbof_config.description or 'Unknown JBOF'
    header = f"-- {jbof_desc} "
    if len(header) > jbof_width - 2:
        header = header[:jbof_width - 5] + ".. "
    header_line = "+" + header + "-" * (jbof_width - len(header) - 2) + "+"
    lines.append(pad_jbof_line(header_line))

    # IOM management and datapath info side by side
    iom1_mgmt = "N/A"
    iom2_mgmt = "N/A"

    if iom_mapping and hasattr(iom_mapping, 'mapping'):
        iom1_info = iom_mapping.mapping.get("IOM1")
        iom2_info = iom_mapping.mapping.get("IOM2")
        iom1_mgmt = (iom1_info.mgmt_ip if iom1_info and iom1_info.mgmt_ip else "N/A")[:15]
        iom2_mgmt = (iom2_info.mgmt_ip if iom2_info and iom2_info.mgmt_ip else "N/A")[:15]
    else:
        iom1_mgmt = (jbof_config.mgmt_ip1 or 'N/A')[:15]
        iom2_mgmt = (jbof_config.mgmt_ip2 or 'N/A')[:15]

    # Calculate column widths for IOM headers based on actual JBOF width
    total_inner_width = jbof_width - 2  # Subtract border characters
    iom1_col_width = total_inner_width // 2
    iom2_col_width = total_inner_width - iom1_col_width
    lines.append(pad_jbof_line(f"| {'IOM1':<{iom1_col_width}}{'IOM2':<{iom2_col_width}} |"))
    lines.append(pad_jbof_line(f"| {'Mgmt: ' + iom1_mgmt:<{iom1_col_width}}{'Mgmt: ' + iom2_mgmt:<{iom2_col_width}} |"))

    # Datapath interfaces
    iom1_interfaces = datapath_interfaces.get("IOM1", {})
    iom2_interfaces = datapath_interfaces.get("IOM2", {})

    for eth_port in JBOFConfig.ETHERNET_PORTS:
        dp_name = "DP1" if eth_port == "Ethernet1" else "DP2"

        # IOM1 datapath
        iom1_ip = "(down)"
        if eth_port in iom1_interfaces and iom1_interfaces[eth_port].status == JBOFConfig.STATUS_SUCCESS:
            interface = iom1_interfaces[eth_port]
            if interface.link_status == JBOFConfig.LINK_UP_STATUS:
                ips = [ip_info.get("address") for ip_info in interface.ip_addresses
                       if ip_info.get("address")]
                if ips:
                    iom1_ip = (ips[0] or "(down)")[:15]

        # IOM2 datapath
        iom2_ip = "(down)"
        if eth_port in iom2_interfaces and iom2_interfaces[eth_port].status == JBOFConfig.STATUS_SUCCESS:
            interface = iom2_interfaces[eth_port]
            if interface.link_status == JBOFConfig.LINK_UP_STATUS:
                ips = [ip_info.get("address") for ip_info in interface.ip_addresses
                       if ip_info.get("address")]
                if ips:
                    iom2_ip = (ips[0] or "(down)")[:15]

        # Format datapath lines with proper column alignment
        iom1_dp_text = f"{dp_name}: {iom1_ip}"
        iom2_dp_text = f"{dp_name}: {iom2_ip}"
        lines.append(pad_jbof_line(f"| {iom1_dp_text:<{iom1_col_width}}{iom2_dp_text:<{iom2_col_width}} |"))

    lines.append(pad_jbof_line("+" + "-" * (jbof_width - 2) + "+"))

    # Drive table header with dynamic column widths - match exact drive row format
    serial_header = f"{'Serial_Number':<{col_widths['serial']}}"
    # Header format must match: |{drive_num:>6} | {iom1_state:<10} |{serial:<width}| {iom2_state:<10} |{flag}|
    header_line = f"|{'Drive':>6} | {'IOM1 State':<10} |{serial_header}| {'IOM2 State':<10} |  |"
    # Create separator by replacing all non-pipe characters with dashes
    separator_line = ''.join('-' if c != '|' else '|' for c in header_line)
    lines.append(pad_jbof_line(header_line))
    lines.append(pad_jbof_line(separator_line))

    # Get drive state flags
    flags = get_drive_state_flags(drives1, drives2)

    # Create unified drive list (up to 24 drives)
    all_drives = {}
    for drive in drives1:
        drive_id = drive.id
        all_drives[drive_id] = {
            "iom1_state": drive.status,
            "iom2_state": "Unknown",
            "serial": drive.serial
        }

    for drive in drives2:
        drive_id = drive.id
        if drive_id in all_drives:
            all_drives[drive_id]["iom2_state"] = drive.status
        else:
            all_drives[drive_id] = {
                "iom1_state": "Unknown",
                "iom2_state": drive.status,
                "serial": drive.serial
            }

    # Generate drive rows
    for drive_num in range(JBOFConfig.DRIVE_RANGE_START, JBOFConfig.DRIVE_RANGE_END):
        drive_id = str(drive_num)

        if drive_id in all_drives:
            drive_info = all_drives[drive_id]
            iom1_state = (drive_info["iom1_state"] or "Unknown")[:10]
            iom2_state = (drive_info["iom2_state"] or "Unknown")[:10]
            serial = drive_info["serial"] or "Unknown"  # No truncation
        else:
            iom1_state = "Absent"
            iom2_state = "Absent"
            serial = "(empty)"

        flag = flags.get(drive_id, " ")

        # Use dynamic serial column width - no truncation
        line = f"|{drive_num:>6} | {iom1_state:<10} |{serial:<{col_widths['serial']}}| {iom2_state:<10} |{flag}|"
        lines.append(pad_jbof_line(line))

    lines.append(pad_jbof_line("+" + "-" * (jbof_width - 2) + "+"))

    return lines


def calculate_column_widths(drives1: List[DriveInfo], drives2: List[DriveInfo],
                            pool_mapping: PoolMappingResult) -> Dict[str, int]:
    """Calculate optimal column widths based on actual data."""
    widths = {
        "device": JBOFConfig.MIN_DEVICE_WIDTH,
        "pool": JBOFConfig.MIN_POOL_WIDTH,
        "uuid": JBOFConfig.MIN_UUID_WIDTH,
        "serial": JBOFConfig.MIN_SERIAL_WIDTH
    }

    # Always account for special device status strings that may appear
    special_device_strings = ["(not_seen)", "(empty)", "nvmeXnX", "nvme132n1"]  # Include longer example
    for device_str in special_device_strings:
        widths["device"] = max(widths["device"], len(device_str))

    # Analyze host box data (pool mappings)
    if pool_mapping and pool_mapping.mappings:
        for mapping in pool_mapping.mappings:
            device = mapping.nvme_device or "(not_seen)"
            pool = mapping.pool_name or ""
            uuid = mapping.partuuid or ""

            widths["device"] = max(widths["device"], len(str(device)))
            widths["pool"] = max(widths["pool"], len(str(pool)))
            widths["uuid"] = max(widths["uuid"], len(str(uuid)))

    # Analyze JBOF box data (drive serials)
    all_drives = {}
    for drive in drives1:
        drive_id = drive.id
        all_drives[drive_id] = drive.serial

    for drive in drives2:
        drive_id = drive.id
        if drive_id not in all_drives:
            all_drives[drive_id] = drive.serial

    for serial in all_drives.values():
        if serial and serial != "Unknown":
            widths["serial"] = max(widths["serial"], len(str(serial)))

    return widths


def create_jbof_visualization(jbof_system: JBOFSystem, node_info: Optional[TrueNASNodeInfoResult] = None) -> str:
    """Create enhanced ASCII visualization of JBOF system with side-by-side layout."""
    # Extract fields from jbof_system for clarity
    jbof_config = jbof_system.config
    drives1 = jbof_system.drives1
    drives2 = jbof_system.drives2
    datapath_interfaces = jbof_system.datapath_interfaces
    rdma_analysis = jbof_system.rdma_analysis
    pool_mapping = jbof_system.pool_mapping
    iom_mapping = jbof_system.iom_mapping

    # Calculate optimal column widths based on actual data
    col_widths = calculate_column_widths(drives1, drives2, pool_mapping)

    # Determine host box position
    position = determine_host_position(rdma_analysis, datapath_interfaces)

    # Create JBOF box with calculated widths
    jbof_lines = create_jbof_box(jbof_config, drives1, drives2, datapath_interfaces, iom_mapping, col_widths)
    jbof_height = len(jbof_lines)

    # Create host box with matching height and calculated widths
    host_lines = create_host_box(pool_mapping, rdma_analysis, node_info, datapath_interfaces,
                                 jbof_height, col_widths, drives1, drives2)

    # Combine boxes side by side
    result_lines = []

    # Skip standalone connectivity lines - show connectivity through box content instead

    # Ensure boxes are same height
    max_lines = max(len(host_lines), len(jbof_lines))

    # Get dynamic widths for padding
    host_width = len(host_lines[0]) if host_lines else JBOFConfig.HOST_MIN_WIDTH
    jbof_width = len(jbof_lines[0]) if jbof_lines else JBOFConfig.DEFAULT_JBOF_WIDTH

    # Pad shorter box to match height with properly sized lines
    while len(host_lines) < max_lines:
        host_lines.append("|" + " " * (host_width - 2) + "|")

    while len(jbof_lines) < max_lines:
        jbof_lines.append("|" + " " * (jbof_width - 2) + "|")

    # Combine host and JBOF boxes with proper spacing
    for i in range(max_lines):
        host_line = host_lines[i]
        jbof_line = jbof_lines[i]

        # Calculate spacing to maintain alignment
        spacing = " " * JBOFConfig.BOX_SPACING

        if position == "left":
            combined_line = host_line + spacing + jbof_line
        else:
            combined_line = jbof_line + spacing + host_line

        result_lines.append(combined_line)

    return "\n".join(result_lines)


def map_jbof_disks_to_pools(jbof_drives, truenas_nvme_devices, partuuid_mapping, zfs_pools) -> PoolMappingResult:
    """Map JBOF drives to ZFS pools using serial numbers and partuuid mappings."""
    if not jbof_drives:
        return PoolMappingResult(
            status="no_jbof_data",
            details="No JBOF drive data available",
            mappings=[],
            summary={"total_drives": 0, "nvme_visible": 0, "pool_assigned": 0}
        )

    if not truenas_nvme_devices:
        return PoolMappingResult(
            status="no_nvme_data",
            details="No TrueNAS NVMe device data available",
            mappings=[],
            summary={"total_drives": len(jbof_drives), "nvme_visible": 0, "pool_assigned": 0}
        )

    # Create mapping from serial number to nvme device path
    serial_to_nvme = {}
    for device in truenas_nvme_devices:
        serial = device.serial_number.strip() if device.serial_number else ""
        device_path = device.device_path
        if serial and device_path:
            # Extract base device name (e.g., "/dev/nvme15n1" -> "nvme15n1")
            base_device = os.path.basename(device_path)
            serial_to_nvme[serial] = base_device

    # Create mapping from base device to partuuid
    device_to_partuuid = {}
    if partuuid_mapping and partuuid_mapping.mapping:
        for partuuid, info in partuuid_mapping.mapping.items():
            base_device = info.base_device
            if base_device:
                device_to_partuuid[base_device] = partuuid

    # Create mapping from partuuid to pool info
    partuuid_to_pool = {}
    for pool in zfs_pools.pools:
        pool_name = pool.get("name", "Unknown")
        topology = pool.get("topology", {})

        # Handle case where topology is None
        if topology is None:
            topology = {}

        # Walk through all vdevs to find disk references
        for vdev_type in ["data", "log", "cache", "spare", "special", "dedup"]:
            for vdev in topology.get(vdev_type, []):
                _extract_disk_refs(vdev, pool_name, partuuid_to_pool)

    # Now map JBOF drives to pools
    drive_mappings = []
    for drive in jbof_drives:
        jbof_serial = drive.serial.strip() if drive.serial else ""
        drive_id = drive.id

        mapping = PoolMapping(
            jbof_drive_id=drive_id,
            jbof_serial=jbof_serial,
            status="unknown"
        )

        if jbof_serial in serial_to_nvme:
            nvme_device = serial_to_nvme[jbof_serial]
            mapping.nvme_device = nvme_device
            mapping.status = "nvme_found"

            if nvme_device in device_to_partuuid:
                partuuid = device_to_partuuid[nvme_device]
                mapping.partuuid = partuuid
                mapping.status = "partuuid_found"

                if partuuid in partuuid_to_pool:
                    pool_info = partuuid_to_pool[partuuid]
                    mapping.pool_name = pool_info.get("pool_name")
                    mapping.pool_status = pool_info.get("pool_status")
                    mapping.vdev_type = pool_info.get("vdev_type")
                    mapping.status = "pool_assigned"
                else:
                    mapping.status = "no_pool"
            else:
                mapping.status = "no_partuuid"
        else:
            mapping.status = "nvme_not_found"

        drive_mappings.append(mapping)

    # Generate summary
    pool_assigned = sum(1 for m in drive_mappings if m.status == "pool_assigned")
    nvme_found = sum(1 for m in drive_mappings
                     if m.status in ["nvme_found", "partuuid_found", "no_pool", "pool_assigned"])

    details = f"✓ {nvme_found}/{len(jbof_drives)} drives visible to TrueNAS"
    if pool_assigned > 0:
        details += f", {pool_assigned} assigned to pools"

    return PoolMappingResult(
        status=JBOFConfig.STATUS_SUCCESS,
        details=details,
        mappings=drive_mappings,
        summary={
            "total_drives": len(jbof_drives),
            "nvme_visible": nvme_found,
            "pool_assigned": pool_assigned
        }
    )


def _extract_disk_refs(vdev, pool_name, partuuid_to_pool):
    """Recursively extract disk references from vdev structure."""
    if isinstance(vdev, dict):
        # Check if this is a disk vdev
        if vdev.get("type") == "DISK":
            path = vdev.get("path", "")
            if "/dev/disk/by-partuuid/" in path:
                partuuid = os.path.basename(path)
                partuuid_to_pool[partuuid] = {
                    "pool_name": pool_name,
                    "pool_status": vdev.get("status", "Unknown"),
                    "vdev_type": "data"  # Could be refined based on context
                }

        # Check children
        children = vdev.get("children", [])
        for child in children:
            _extract_disk_refs(child, pool_name, partuuid_to_pool)


def _collect_jbof_data_from_ip(mgmt_ip: str, jbof_config: JBOFConfiguration
                               ) -> tuple[DriveInventoryResult, DatapathInterfaceResult, bool]:
    """Collect drive inventory and datapath interfaces from a single management IP.

    Args:
        mgmt_ip: Management IP address to connect to
        jbof_config: JBOF configuration containing credentials and other settings

    Returns:
        tuple: (drive_result, datapath_result, connectivity_success) where:
        - drive_result: DriveInventoryResult with drive data or error status
        - datapath_result: DatapathInterfaceResult with interface data or error status
        - connectivity_success: bool indicating if connection was successful
    """
    empty_drive_result = DriveInventoryResult(status="no_connection", details="No connection", drives=[])
    empty_datapath_result = DatapathInterfaceResult(status="no_connection", details="No connection", interfaces={})

    if not mgmt_ip or not jbof_config.mgmt_username or not jbof_config.mgmt_password:
        return empty_drive_result, empty_datapath_result, False

    # Check connectivity once
    conn_result = check_redfish_connectivity(mgmt_ip, jbof_config.uuid)
    if conn_result.status != JBOFConfig.CONNECTION_SUCCESS:
        return empty_drive_result, empty_datapath_result, False

    # Get drive inventory
    drive_result = get_drive_inventory(mgmt_ip, jbof_config.mgmt_username, jbof_config.mgmt_password)

    # Get datapath interfaces
    datapath_result = get_datapath_interfaces(mgmt_ip, jbof_config.mgmt_username, jbof_config.mgmt_password)

    return drive_result, datapath_result, True


def gather_jbof_data(jbofs: List[JBOFConfiguration]) -> Optional[JBOFSystemData]:
    """Gather all JBOF information once to avoid duplication between display modes.

    Args:
        jbofs: List of JBOFConfiguration objects from TrueNAS API containing
               management IPs, credentials, UUIDs, and other configuration data.

    Returns:
        JBOFSystemData containing:
        - truenas_info: TrueNASSystemInfo with consolidated TrueNAS data
        - jbof_systems: List of JBOFSystem objects with complete JBOF information

        Returns None if no JBOFs provided.
    """
    if not jbofs:
        return None

    # Get common TrueNAS data once
    truenas_nvme_result = get_truenas_nvme_devices()
    truenas_nvme_devices = truenas_nvme_result.devices
    partuuid_result = get_partuuid_to_nvme_mapping()
    zfs_pools_result = get_zfs_pools()
    node_info = get_truenas_node_info()
    rdma_interfaces_result = get_truenas_rdma_interfaces()

    # Create TrueNAS system info
    truenas_info = TrueNASSystemInfo(
        nvme_devices=truenas_nvme_result,
        partuuid_mappings=partuuid_result,
        zfs_pools=zfs_pools_result,
        node_info=node_info,
        rdma_interfaces=rdma_interfaces_result
    )

    # Process each JBOF and create JBOFSystem objects directly
    jbof_systems = []
    for jbof_config in jbofs:
        # Map management IPs to IOMs first
        iom_mapping = map_management_ips_to_ioms(jbof_config)

        # Collect data from both management IPs
        drive_result1, datapath_result1, ip1_success = _collect_jbof_data_from_ip(jbof_config.mgmt_ip1, jbof_config)
        drive_result2, datapath_result2, ip2_success = _collect_jbof_data_from_ip(jbof_config.mgmt_ip2, jbof_config)

        # Extract drives from successful results
        drives1 = drive_result1.drives if drive_result1.status == JBOFConfig.STATUS_SUCCESS else []
        drives2 = drive_result2.drives if drive_result2.status == JBOFConfig.STATUS_SUCCESS else []

        # Use datapath interfaces from first successful connection
        datapath_interfaces = datapath_result1.interfaces if ip1_success else datapath_result2.interfaces

        # RDMA analysis
        rdma_analysis = analyze_rdma_connectivity(rdma_interfaces_result, node_info, datapath_interfaces)

        # Map disks to pools
        primary_drives = get_primary_drives(drives1, drives2)
        pool_mapping = map_jbof_disks_to_pools(primary_drives, truenas_nvme_devices,
                                               partuuid_result, zfs_pools_result)

        # Create JBOFSystem object directly
        jbof_system = JBOFSystem(
            name=jbof_config.description or f'JBOF {jbof_config.index}',
            index=jbof_config.index,
            uuid=jbof_config.uuid,
            description=jbof_config.description,
            config=jbof_config,
            iom1=(iom_mapping.mapping.get("IOM1", IOMInfo(mgmt_ip=None, status="unknown"))
                  if iom_mapping and iom_mapping.mapping
                  else IOMInfo(mgmt_ip=None, status="unknown")),
            iom2=(iom_mapping.mapping.get("IOM2", IOMInfo(mgmt_ip=None, status="unknown"))
                  if iom_mapping and iom_mapping.mapping
                  else IOMInfo(mgmt_ip=None, status="unknown")),
            iom_mapping=iom_mapping,
            drives1=drives1,
            drives2=drives2,
            datapath_interfaces=datapath_interfaces,
            rdma_analysis=rdma_analysis,
            pool_mapping=pool_mapping
        )
        jbof_systems.append(jbof_system)

    return JBOFSystemData(
        truenas_info=truenas_info,
        jbof_systems=jbof_systems
    )


def display_jbof_simple_with_data(data: JBOFSystemData) -> None:
    """Display basic JBOF information using pre-gathered data.

    Args:
        data: Pre-gathered JBOF data from gather_jbof_data() containing
              TrueNAS system information and JBOF systems.
    """
    if not data or not data.jbof_systems:
        message = "No JBOFs found or unable to connect to TrueNAS."
        logger.warning(message)
        print(message)
        return

    jbof_systems = data.jbof_systems
    truenas_info = data.truenas_info

    print(f"Found {len(jbof_systems)} JBOF system(s):")
    print(JBOFConfig.SEPARATOR_50)

    # Display common TrueNAS information
    print("Checking TrueNAS NVMe devices...")
    print(f"TrueNAS NVMe Status: {truenas_info.nvme_devices.details}")
    print("Checking partuuid mappings...")
    print(f"Partuuid Mappings: {truenas_info.partuuid_mappings.details}")
    print("Checking ZFS pools...")
    print(f"ZFS Pools: {truenas_info.zfs_pools.details}")
    print("Checking TrueNAS node status...")
    print(f"TrueNAS Node: {truenas_info.node_info.details}")
    print("Checking TrueNAS RDMA interfaces...")
    print(f"RDMA Interfaces: {truenas_info.rdma_interfaces.details}")
    print()

    # Display each JBOF
    for jbof_system in jbof_systems:
        print(f"\nJBOF {jbof_system.index}:")
        print(f"  Description: {jbof_system.description}")
        print(f"  Index: {jbof_system.index}")
        print(f"  UUID: {jbof_system.uuid}")

        # Display management interface details
        mgmt_ip1 = jbof_system.config.mgmt_ip1 or 'N/A'
        mgmt_ip2 = jbof_system.config.mgmt_ip2 or 'N/A'
        print(f"  Management IP1: {mgmt_ip1}")
        if mgmt_ip1 and mgmt_ip1 != 'N/A':
            conn1 = check_redfish_connectivity(mgmt_ip1, jbof_system.uuid)
            status_symbol = "✓" if conn1.status == JBOFConfig.CONNECTION_SUCCESS else "✗"
            print(f"    Redfish Status: {status_symbol} {conn1.details}")

        print(f"  Management IP2: {mgmt_ip2}")
        if mgmt_ip2 and mgmt_ip2 != 'N/A':
            conn2 = check_redfish_connectivity(mgmt_ip2, jbof_system.uuid)
            status_symbol = "✓" if conn2.status == JBOFConfig.CONNECTION_SUCCESS else "✗"
            print(f"    Redfish Status: {status_symbol} {conn2.details}")

        # Display drive comparison
        drives1 = jbof_system.drives1
        drives2 = jbof_system.drives2
        present_count1 = len([d for d in drives1 if d.status.lower() not in JBOFConfig.DRIVE_ABSENT_STATES])
        present_count2 = len([d for d in drives2 if d.status.lower() not in JBOFConfig.DRIVE_ABSENT_STATES])

        if present_count1 == present_count2:
            print(f"  Drive Comparison: ✓ Both interfaces see {present_count1} drives present")
        else:
            print(f"  Drive Comparison: ✗ Mismatch - IOM1: {present_count1}, IOM2: {present_count2}")

        print(f"    Slot Utilization: {present_count1}/{JBOFConfig.STANDARD_SLOTS} slots occupied")

        # Display TrueNAS drive visibility with JBOF-specific summary
        pool_mapping = jbof_system.pool_mapping
        if pool_mapping and pool_mapping.mappings:
            total_drives = len(pool_mapping.mappings)
            visible_statuses = ["nvme_found", "partuuid_found", "no_pool", "no_partuuid", "pool_assigned"]
            visible_drives = len([m for m in pool_mapping.mappings if m.status in visible_statuses])
            pool_assigned = len([m for m in pool_mapping.mappings if m.status == "pool_assigned"])
            print(f"  TrueNAS NVMe Visibility: {visible_drives}/{total_drives} drives visible, "
                  f"{pool_assigned} in pools")

        # Display ZFS pool associations
        if pool_mapping and pool_mapping.mappings:
            print("  ZFS Pool Associations:")
            # Group mappings by pool name
            pool_groups = {}
            for mapping in pool_mapping.mappings:
                if mapping.pool_name and mapping.status == "pool_assigned":
                    pool_name = mapping.pool_name
                    if pool_name not in pool_groups:
                        pool_groups[pool_name] = []
                    pool_groups[pool_name].append(mapping)

            for pool_name, pool_disks in pool_groups.items():
                print(f"    {pool_name}: {len(pool_disks)} drives")

        # Display RDMA connectivity summary
        rdma_analysis = jbof_system.rdma_analysis
        if rdma_analysis and hasattr(rdma_analysis, 'summary'):
            summary_text = rdma_analysis.summary
        else:
            summary_text = 'No connectivity found'
        rdma_summary = f"RDMA Status: {summary_text}"
        print(f"  {rdma_summary}")


def display_jbof_visual_with_data(data: JBOFSystemData) -> None:
    """Display JBOF information with ASCII visualization using pre-gathered data.

    Args:
        data: Pre-gathered JBOF data from gather_jbof_data() containing
              TrueNAS system information and JBOF systems.
    """
    if not data or not data.jbof_systems:
        message = "No JBOFs found or unable to connect to TrueNAS."
        logger.warning(message)
        print(message)
        return

    truenas_info = data.truenas_info
    jbof_systems = data.jbof_systems

    for jbof_system in jbof_systems:
        print(f"\nJBOF {jbof_system.index} Visualization:")
        print(JBOFConfig.SEPARATOR_80)

        # Create visualization with simplified interface
        visualization = create_jbof_visualization(jbof_system, truenas_info.node_info)
        print(visualization)

        print()


def main() -> None:
    """Main function to run the JBOF visualizer.

    Parses command line arguments, retrieves JBOF configuration from TrueNAS API,
    gathers all necessary data once, and displays results in the requested format
    (simple, visual, or both modes).
    """
    parser = argparse.ArgumentParser(description="TrueNAS JBOF Visualizer")
    parser.add_argument("-v", "--visual", action="store_true",
                        help="Display visual ASCII representation of JBOFs")
    parser.add_argument("-s", "--simple", action="store_true",
                        help="Display simple text output (default)")
    parser.add_argument("-b", "--both", action="store_true",
                        help="Display both simple and visual output (gather data once)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.WARNING
    setup_logging(log_level)

    logger.debug("Starting TrueNAS JBOF Visualizer")

    # Default to simple if no mode specified
    if not args.visual and not args.simple and not args.both:
        args.simple = True

    print("TrueNAS JBOF Visualizer")
    if args.both:
        print("Both Modes (Simple + Visual)")
        logger.debug("Running in both modes")
    elif args.visual:
        print("Visual Mode")
        logger.debug("Running in visual mode")
    else:
        print("Simple Mode")
        logger.debug("Running in simple mode")
    print(JBOFConfig.SEPARATOR_25)

    jbofs = get_jbof_info()
    logger.debug(f"Found {len(jbofs)} JBOF configuration(s)")

    # Sort JBOFs by index for consistent ordering
    jbofs = sorted(jbofs, key=lambda x: x.index)

    # Always gather data once using centralized function
    logger.debug("Gathering JBOF data from all sources")
    data = gather_jbof_data(jbofs)

    if args.both:
        # Display both ways using pre-gathered data
        if data:
            display_jbof_simple_with_data(data)
            print("\n" + JBOFConfig.SEPARATOR_50)
            print("VISUAL REPRESENTATION")
            print(JBOFConfig.SEPARATOR_50)
            display_jbof_visual_with_data(data)
    elif args.visual:
        # Visual mode using pre-gathered data
        if data:
            display_jbof_visual_with_data(data)
    else:
        # Simple mode using pre-gathered data
        if data:
            display_jbof_simple_with_data(data)


if __name__ == "__main__":
    main()
