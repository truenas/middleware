import argparse
import pathlib
import subprocess

import init_cluster
import init_gluster


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


def setup_api_results_dir():
    # create the results directory
    path = pathlib.Path(pathlib.os.getcwd()).joinpath('results')
    path.mkdir(exist_ok=True)

    # add the file that will store the api results
    path = path.joinpath('results.xml')
    try:
        path.unlink()
    except FileNotFoundError:
        pass

    path.touch()

    return path.as_posix()


def setup_pytest_command(args, results_path):
    cmd = ['pytest', '-v', '-rfesp', f'--junit-xml={results_path}']

    # pytest is clever enough to search the "tests" subdirectory
    # and look at the argument that is passed and figure out if
    # it's a file or a directory so we don't need to do anything
    # fancy other than pass it on
    if args.test_file:
        cmd.append(args.test_file)
    elif args.test_dir:
        cmd.append(args.test_dir)

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


if __name__ == '__main__':
    main()
