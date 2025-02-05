import argparse
import sys
from enum import StrEnum

from protocols import iscsi_scsi_connection


class Pattern(StrEnum):
    ZEROS = 'zeros'
    DEADBEEF = 'deadbeef'


IQN_BASE = 'iqn.2005-10.org.freenas.ctl'
LBA = 0
NUM_BLOCKS = 1


def main(args):
    iqn = f'{IQN_BASE}:{args.target}'
    with iscsi_scsi_connection(args.ip, iqn) as s:
        match args.operation:
            case 'read':
                r = s.read16(LBA, NUM_BLOCKS)
                print(r.datain)
            case 'write':
                match args.pattern:
                    case Pattern.ZEROS:
                        pat = bytearray(512)
                    case Pattern.DEADBEEF:
                        pat = bytearray.fromhex('deadbeef') * 128
                s.writesame16(LBA, NUM_BLOCKS, pat)
                s.synchronizecache10(LBA, NUM_BLOCKS)

    sys.exit(0)


def parse_args():
    parser = argparse.ArgumentParser(prog='target')
    subparsers = parser.add_subparsers(dest='operation', help='Operation to perform on target', required=True)

    # Use this under each subparser for ordering purposes.
    def add_common(sub_parser):
        sub_parser.add_argument('--target', default='test1', help='Name of the TrueNAS target; default test1')
        sub_parser.add_argument('--ip', required=True, help='IP address to be used to connect to target')

    # READ
    parser_r = subparsers.add_parser('read', help='Read from the specified target')
    add_common(parser_r)

    # WRITE
    parser_w = subparsers.add_parser('write', help='Write to the specified target')
    add_common(parser_w)
    parser_w.add_argument('--pattern', type=Pattern, choices=list(Pattern), required=True)

    return parser.parse_args()


if __name__ == '__main__':
    main(parse_args())
