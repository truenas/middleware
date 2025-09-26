# This script should be run locally from a TrueNAS VM. It runs all tests
# contained within the tests/unit directory as well as middleware specific unit
# tests contained within src/middlewared/middlewared/pytest/unit.
#
# NOTE: this requires `make install_tests` to have been run on the TrueNAS VM.

import argparse
import middlewared
import os
import pytest
import sys

from contextlib import contextmanager
from collections.abc import Generator
from dataclasses import dataclass
from junitparser import JUnitXml
from shutil import copytree, rmtree
from truenas_api_client import Client
from uuid import uuid4

DESCRIPTION = (
    'Run unit tests from the specified middleware git repository on the '
    'current TrueNAS server (version 25.04 or later). Exit code is one of '
    'pytest exit codes with zero indicating success.'
)

UNIT_TESTS = 'tests/unit'
MIDDLEWARE_MODULE_PATH = '/usr/lib/python3/dist-packages/middlewared'
MIDDLEWARE_PYTEST = 'src/middlewared/middlewared/pytest'
MIDDLEWARE_UNIT_TESTS = os.path.join(MIDDLEWARE_PYTEST, 'unit')
MIDDLEWARE_PYTEST_MODULE = os.path.join(MIDDLEWARE_MODULE_PATH, 'pytest')
RESULT_FILE = 'unit_tests_result.xml'
PYTEST_CONFTEST_FILE = 'tests/conftest.py'

if not os.path.exists(MIDDLEWARE_MODULE_PATH):
    # If middlware has been reinstalled then we should try to find where it's located
    MIDDLEWARE_MODULE_PATH = os.path.dirname(os.path.abspath(middlewared.__file__))


@dataclass()
class UnitTestRun:
    tests_dir: str
    exit_code: pytest.ExitCode = pytest.ExitCode.NO_TESTS_COLLECTED
    junit_file: str | None = None


def run_tests(data: UnitTestRun) -> UnitTestRun:
    junit_file = f'unit_tests_result_{uuid4()}.xml'

    data.exit_code = pytest.main([
        '--disable-warnings', '-vv',
        '-o', 'junit_family=xunit2',
        '--junitxml', junit_file,
        data.tests_dir
    ])

    if data.exit_code is not pytest.ExitCode.OK:
        print(
            f'{data.tests_dir}: tests failed with code: {data.exit_code}',
            file=sys.stderr
        )

    data.junit_file = junit_file
    return data


def run_unit_tests(repo_dir: str) -> pytest.ExitCode:
    """
    Iterate through our unit test sources and create a unified junit xml file
    for the overall test results.
    """
    xml_out = JUnitXml()
    exit_code = pytest.ExitCode.NO_TESTS_COLLECTED
    for test_dir in (
        os.path.join(repo_dir, UNIT_TESTS),
        os.path.join(repo_dir, MIDDLEWARE_UNIT_TESTS),
    ):
        if not os.path.exists(test_dir):
            raise FileNotFoundError(f'{test_dir}: unit test directory does not exist')

        data = run_tests(UnitTestRun(tests_dir=test_dir))
        xml_out += JUnitXml.fromfile(data.junit_file)
        try:
            os.remove(data.junit_file)
        except Exception:
            pass

        match data.exit_code:
            case pytest.ExitCode.NO_TESTS_COLLECTED:
                # We'll treat this as a partial failure because we still want our
                # test results from other runs, but don't want an overall misleading
                # result.
                print(
                    f'{test_dir}: not tests collected. Treating as partial failure.',
                    file=sys.stderr
                )
                if exit_code is pytest.ExitCode.OK:
                    exit_code = pytest.ExitCode.TESTS_FAILED

            case pytest.ExitCode.OK:
                # If this is our first OK test, set exit code
                # otherwise preserve existing
                if exit_code is pytest.ExitCode.NO_TESTS_COLLECTED:
                    exit_code = data.exit_code

            case _:
                # exit codes are an IntEnum. Preserve worst case
                if exit_code < data.exit_code:
                    exit_code = data.exit_code

    xml_out.write(RESULT_FILE)
    return exit_code


@contextmanager
def disable_api_test_config(path: str) -> Generator[None, None, None]:
    """ prevent API tests conftest from being applied """
    os.rename(
        os.path.join(path, PYTEST_CONFTEST_FILE),
        os.path.join(path, f'{PYTEST_CONFTEST_FILE}.tmp')
    )

    try:
        yield
    finally:
        os.rename(
            os.path.join(path, f'{PYTEST_CONFTEST_FILE}.tmp'),
            os.path.join(path, PYTEST_CONFTEST_FILE)
        )


@contextmanager
def setup_middleware_tests(path: str) -> Generator[None, None, None]:
    """ temporarily setup our pytest tests in the python dir """
    try:
        copytree(
            os.path.join(path, MIDDLEWARE_PYTEST),
            os.path.join(MIDDLEWARE_PYTEST_MODULE),
            dirs_exist_ok=True
        )
        yield
    finally:
        rmtree(MIDDLEWARE_PYTEST_MODULE)


def main() -> None:
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument(
        '-p', '--path',
        help='Path to local copy of middleware git repository',
        default='./middleware'
    )

    # lazy check to verify we're on a TrueNAS server
    with Client() as c:
        assert c.call('system.ready')

    args = parser.parse_args()
    with disable_api_test_config(args.path):
        with setup_middleware_tests(args.path):
            exit_code = run_unit_tests(args.path)

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
