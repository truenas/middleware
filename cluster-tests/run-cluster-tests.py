import argparse
import sys
import pathlib
import subprocess

import init_cluster


def setup_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--initialize-cluster',
        action='store_true',
        default=False,
        help='Setup the cluster for API testing.'
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
    cmd = [f'pytest-{sys.version_info.major}', '-v', '-rfesp', f'--junit-xml={results_path}']
    if not args.test_file and not args.test_dir:
        cmd.append('tests')
    elif args.test_file:
        if not args.test_file.startswith('tests'):
            args.test_file = pathlib.Path('tests').joinpath(args.test_file).as_posix()
        cmd.append(args.test_file)
    elif args.test_dir:
        if not args.test_dir.startswith('tests'):
            args.test_dir = pathlib.Path('tests').joinpath(args.test_dir).as_posix()
        cmd.append(args.test_dir)

    print(cmd)
    return cmd


def main():
    args = setup_args()
    if args.initialize_cluster:
        print('Initializing cluster')
        init_cluster.init()

    print('Setting up API results directory')
    results_path = setup_api_results_dir()

    print('Running API tests')
    subprocess.call(setup_pytest_command(args, results_path))


if __name__ == '__main__':
    main()
