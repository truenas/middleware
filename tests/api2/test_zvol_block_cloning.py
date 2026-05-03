from middlewared.test.integration.assets.pool import dataset, pool
from middlewared.test.integration.utils import ssh


_1GiB = 1073741824
_1MiB = 1048576
_VOLBLOCKSIZE = "16K"
_EXPECTED_SHARED_BLOCKS = _1MiB // (16 * 1024)


def test_zvol_block_cloning():
    """
    Verify zvol-to-zvol copy_file_range produces shared L0 blocks (block cloning),
    not an independent copy. Identical L0 DVA+checksum entries between src and dst
    in zdb output prove the destination references the source's blocks.
    """
    args = {
        "type": "VOLUME",
        "volsize": _1GiB,
        "volblocksize": _VOLBLOCKSIZE,
    }
    with dataset("bclone_src", args) as src, dataset("bclone_dst", args) as dst:
        ssh(f"dd if=/dev/urandom of=/dev/zvol/{src} bs=1M count=1 oflag=direct")
        ssh(f"zpool sync {pool}")
        ssh(
            f"python3 -c '"
            f"import os; "
            f'fi = os.open("/dev/zvol/{src}", os.O_RDONLY | os.O_DIRECT); '
            f'fo = os.open("/dev/zvol/{dst}", os.O_WRONLY | os.O_DIRECT); '
            f"assert os.copy_file_range(fi, fo, {_1MiB}, 0, 0) == {_1MiB}; "
            f"os.close(fi); os.close(fo)'"
        )
        ssh(f"zpool sync {pool}")
        # Filter to L0 lines with a real DVA, excluding the per-object dnode
        # block (always different between zvols) and EMBEDDED hole markers
        # (identical strings that aren't real shared blocks).
        awk = "awk '/ L0 / && /DVA/ && !/dnode/ { print l++, $3, $7 }'"
        shared_count = int(
            ssh(
                f"zdb -vvvvv {src} | {awk} > /tmp/bclone_src.zdb && "
                f"zdb -vvvvv {dst} | {awk} > /tmp/bclone_dst.zdb && "
                f"sort -n /tmp/bclone_src.zdb /tmp/bclone_dst.zdb | uniq -d | wc -l"
            ).strip()
        )
        assert shared_count == _EXPECTED_SHARED_BLOCKS, (
            f"expected {_EXPECTED_SHARED_BLOCKS} shared L0 blocks "
            f"(1 MiB / {_VOLBLOCKSIZE}), got {shared_count}"
        )
