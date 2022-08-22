import argparse
import pathlib
import subprocess
from xml.etree import ElementTree as etree

import init_cluster
import init_gluster
from config import CLEANUP_TEST_DIR


def setup_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--initialize-cluster',
        action='store_true',
        default=False,
        help='Setup the cluster for API testing.'
    )
    parser.add_argument(
        '--initialize-gluster',
        action='store_true',
        default=False,
        help='Setup the gluster cluster'
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--test-dir',
        default=False,
        help='Relative path to the test directory (i.e. tests/smb)'
    )
    group.add_argument(
        '--test-file',
        default=False,
        help='Relative path to the test file (i.e. tests/smb/test_blah.py)'
    )

    return parser.parse_args()


def setup_api_results_dir(resultsfile='results.xml'):
    # create the results directory
    path = pathlib.Path(pathlib.os.getcwd()).joinpath('results')
    path.mkdir(exist_ok=True)

    # add the file that will store the api results
    path = path.joinpath(resultsfile)
    try:
        path.unlink()
    except FileNotFoundError:
        pass

    path.touch()

    return path.as_posix()


def setup_pytest_command(args, results_path, ignore=True):
    cmd = ['pytest', '-v', '-rfesp', '-o', 'junit_family=xunit2', f'--junit-xml={results_path}']

    # pytest is clever enough to search the "tests" subdirectory
    # and look at the argument that is passed and figure out if
    # it's a file or a directory so we don't need to do anything
    # fancy other than pass it on
    if args.test_file:
        cmd.append(args.test_file)
    elif args.test_dir:
        cmd.append(args.test_dir)

    if ignore:
        cmd.append(f'--ignore={CLEANUP_TEST_DIR}')

    return cmd


def main():
    args = setup_args()
    if args.initialize_cluster:
        print('Initializing cluster')
        init_cluster.init()

    if args.initialize_gluster:
        print('Setting up gluster')
        init_gluster.init()

    print('Setting up API results directory')
    results_path = setup_api_results_dir()

    print('Running API tests')
    subprocess.call(setup_pytest_command(args, results_path))

    """
    We have integration tests that _MUST_ be called after all other
    tests complete. There isn't an "easy" way of doing this that we've
    found so we simply call pytest again specifying the "cleanup" directory
    explicitly. Specifying that directory ensures only the tests in that
    directory run.
    """
    with open(results_path) as f:
        # make sure there were no failures before we continue on running
        # the cleanup tests
        err = 'There are previous API failures. Skipping API cleanup tests'
        assert dict(etree.fromstring(f.read()))['failures'] == '0', err

    print('Setting up cleanup API results file')
    cleanup_results_path = setup_api_results_dir(resultsfile='cleanup-results.xml')

    print('Running cleanup API tests')
    args.test_dir = CLEANUP_TEST_DIR  # overwrite test_dir args
    subprocess.call(setup_pytest_command(args, cleanup_results_path, ignore=False))


if __name__ == '__main__':
    main()
