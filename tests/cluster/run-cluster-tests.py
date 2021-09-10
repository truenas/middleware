import argparse

from initialize_cluster import init_cluster


def setup_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--initialize-cluster',
        action='store_true',
        default=False,
        help='Setup the cluster for API testing.'
    )

    return parser.parse_args()


def main():
    args = setup_args()
    if args.initialize_cluster:
        print('Initializing cluster')
        init_cluster()


if __name__ == '__main__':
    main()
