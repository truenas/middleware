import sys

from .context import Context

TEST_DIR_TO_RESULT = {
    'api2': 'results/api_v2_tests_result.xml',
    'directory_services': 'results/directoryservices_tests_result.xml',
    'stig': 'results/stig_tests_result.xml',
    'sharing_protocols': 'results/sharing_protocols_tests_result.xml',
    'sharing_protocols/fibre_channel': 'results/sharing_protocols_fibre_channel_tests_result.xml',
    'sharing_protocols/iscsi': 'results/sharing_protocols_iscsi_tests_result.xml',
    'sharing_protocols/nfs': 'results/sharing_protocols_nfs_tests_result.xml',
    'sharing_protocols/nvmet': 'results/sharing_protocols_nvmet_tests_result.xml',
    'sharing_protocols/smb': 'results/sharing_protocols_smb_tests_result.xml',
    'cloud': 'results/cloud_tests_result.xml',
    'vm': 'results/vm_result.xml',
}


def get_pytest_command(ctx: Context) -> list[str]:
    callargs = []

    if ctx.no_capture:
        callargs.append('-s')

    if ctx.log_cli_level:
        callargs.append('--log-cli-level')
        callargs.append(ctx.log_cli_level)

    if ctx.verbose:
        callargs.append("-" + "v" * ctx.verbose)

    if ctx.exit_first:
        callargs.append("-x")

    if ctx.show_locals:
        callargs.append('--showlocals')

    # Use the right python version to start pytest with sys.executable
    # So that we can support virtualenv python pytest.
    pytest_command = [
        sys.executable,
        '-m',
        'pytest'
    ] + callargs + [
        "-o", "junit_family=xunit2",
        '--timeout=300',
        "--junitxml",
        TEST_DIR_TO_RESULT[ctx.test_dir],
    ]
    if ctx.testexpr:
        pytest_command.extend(['-k', ctx.testexpr])

    if ctx.tests:
        pytest_command.extend(list(map(lambda s: parse_test_name_prefix_dir(ctx, s), ctx.tests.split(','))))
    else:
        pytest_command.append(parse_test_name_prefix_dir(ctx, ctx.test))

    return pytest_command


def parse_test_name(ctx: Context, test: str) -> str:
    test = test.removeprefix(f"{ctx.test_dir}/")
    test = test.removeprefix(f"{ctx.test_dir}.")
    if ".py" not in test and test.count(".") == 1:
        # Test name from Jenkins
        filename, testname = test.split(".")
        return f"{filename}.py::{testname}"

    return test


def parse_test_name_prefix_dir(ctx: Context, test_name: str) -> str:
    name = parse_test_name(ctx, test_name)
    if name.startswith('/'):
        return name
    else:
        return f"{ctx.test_dir}/{name}"
