import argparse
from dataclasses import dataclass


@dataclass
class RunArgs:
    ip: str
    password: str
    interface: str

    ip2: str
    vip: str

    ha: bool
    ha_license: str
    ha_license_path: str | None

    test: str
    tests: str | None
    test_dir: str
    testexpr: str | None

    update: bool
    extended_tests: bool
    returncode: bool

    verbose: int
    exit_first: bool
    no_capture: bool
    show_locals: bool
    log_cli_level: str | None

    isns_ip: str
    pool_name: str
    vm_name: str | None
    hostname: str | None

    dev_test: bool


def parse(args=None) -> RunArgs:
    parser = argparse.ArgumentParser(description='Run TrueNAS integration tests')

    conn = parser.add_argument_group('connection')
    # required=True + nargs='?' means the flag must be present but its value is
    # optional: bare -i/-p/-I (without a value) set the field to '' via const.
    conn.add_argument(
        '-i', '--ip', nargs='?', const='', required=True,
        metavar='ADDR',
        help='IP address of the TrueNAS system under test',
    )
    conn.add_argument(
        '-p', '--password', nargs='?', const='', required=True,
        metavar='SECRET',
        help='password for the TrueNAS root user',
    )
    conn.add_argument(
        '-I', '--interface', nargs='?', const='', required=True,
        metavar='IFACE',
        help='network interface TrueNAS is bound to',
    )

    ha = parser.add_argument_group('HA')
    ha.add_argument(
        '--ha', action='store_true',
        help='run tests against an HA pair',
    )
    ha.add_argument(
        '--ip2', default='', metavar='ADDR',
        help='B-controller IPv4 address for HA pairs',
    )
    ha.add_argument(
        '--vip', default='', metavar='ADDR',
        help='virtual IP (IPv4) for HA failover',
    )
    ha.add_argument(
        '--ha_license', default='', metavar='B64',
        help='base64-encoded HA license string',
    )
    ha.add_argument(
        '--ha-license-path', dest='ha_license_path', default=None, metavar='PATH',
        help='path to a file containing the HA license (read at startup)',
    )

    sel = parser.add_argument_group('test selection')
    sel.add_argument(
        '-t', '--test', nargs='?', const='', default='', metavar='NAME',
        help='single test file or name to run',
    )
    sel.add_argument(
        '--tests', default=None, metavar='NAME[,NAME...]',
        help='comma-separated list of test files/names to pass to pytest',
    )
    sel.add_argument(
        '--test_dir', default='api2', metavar='DIR',
        help='tests subdirectory to target (default: %(default)s)',
    )
    sel.add_argument(
        '-k', dest='testexpr', default=None, metavar='EXPR',
        help='pytest -k expression for filtering tests by name',
    )

    behaviour = parser.add_argument_group('test behaviour')
    behaviour.add_argument(
        '--update', action='store_true',
        help='enable update tests',
    )
    behaviour.add_argument(
        '--extended_tests', action='store_true',
        help='run the extended test suite',
    )
    behaviour.add_argument(
        '--returncode', action='store_true',
        help='propagate the pytest exit code to the calling shell',
    )

    output = parser.add_argument_group('pytest output')
    output.add_argument(
        '-v', dest='verbose', action='count', default=0,
        help='increase pytest verbosity (may be repeated)',
    )
    output.add_argument(
        '-x', dest='exit_first', action='store_true',
        help='stop after the first test failure',
    )
    output.add_argument(
        '-s', dest='no_capture', action='store_true',
        help='disable pytest output capture',
    )
    output.add_argument(
        '--show_locals', action='store_true',
        help='show local variables in pytest failure output',
    )
    output.add_argument(
        '--log-cli-level', dest='log_cli_level', default=None, metavar='LEVEL',
        help='log level for pytest live CLI logging (e.g. DEBUG)',
    )

    infra = parser.add_argument_group('infrastructure')
    infra.add_argument(
        '--isns_ip', default='10.234.24.50', metavar='ADDR',
        help='IP address of the iSNS server / isns01.qe.ixsystems.net (default: %(default)s)',
    )
    infra.add_argument(
        '--pool', dest='pool_name', default='tank', metavar='NAME',
        help='name of the ZFS pool under test (default: %(default)s)',
    )
    infra.add_argument(
        '--vm-name', dest='vm_name', default=None, metavar='NAME',
        help='name of the Bhyve VM used in VM tests',
    )
    infra.add_argument(
        '--hostname', default=None, metavar='NAME',
        help='hostname override; auto-generated when omitted',
    )

    parser.add_argument(
        '--dev-test', dest='dev_test', action='store_true',
        help=argparse.SUPPRESS,
    )

    ns = parser.parse_args(args)
    return RunArgs(**vars(ns))
