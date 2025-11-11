import pytest
from middlewared.utils.mount import __mntent_dict, __parse_to_mnt_id, __create_tree


fake_mntinfo = r"""21 26 0:19 / /sys rw,nosuid,nodev,noexec,relatime shared:7 - sysfs sysfs rw
22 26 0:20 / /proc rw,nosuid,nodev,noexec,relatime shared:12 - proc proc rw
23 26 0:5 / /dev rw,nosuid,relatime shared:2 - devtmpfs udev rw,size=1841320k,nr_inodes=460330,mode=755,inode64
24 23 0:21 / /dev/pts rw,nosuid,noexec,relatime shared:3 - devpts devpts rw,gid=5,mode=620,ptmxmode=000
25 26 0:22 / /run rw,nosuid,nodev,noexec,relatime shared:5 - tmpfs tmpfs rw,size=402344k,mode=755,inode64
26 1 0:23 / / rw,relatime shared:1 - zfs boot-pool/ROOT/22.12-MASTER-20220616-071633 rw,xattr,noacl
27 21 0:6 / /sys/kernel/security rw,nosuid,nodev,noexec,relatime shared:8 - securityfs securityfs rw
28 23 0:24 / /dev/shm rw,nosuid,nodev shared:4 - tmpfs tmpfs rw,inode64
29 25 0:25 / /run/lock rw,nosuid,nodev,noexec,relatime shared:6 - tmpfs tmpfs rw,size=5120k,inode64
30 21 0:26 / /sys/fs/cgroup rw,nosuid,nodev,noexec,relatime shared:9 - cgroup2 cgroup2 rw,nsdelegate,memory_recursiveprot
31 21 0:27 / /sys/fs/pstore rw,nosuid,nodev,noexec,relatime shared:10 - pstore pstore rw
32 21 0:28 / /sys/fs/bpf rw,nosuid,nodev,noexec,relatime shared:11 - bpf bpf rw,mode=700
33 22 0:29 / /proc/sys/fs/binfmt_misc rw,relatime shared:13 - autofs systemd-1 rw,fd=30,pgrp=1,timeout=0,minproto=5,maxproto=5,direct,pipe_ino=12795
34 23 0:30 / /dev/hugepages rw,relatime shared:14 - hugetlbfs hugetlbfs rw,pagesize=2M
35 23 0:18 / /dev/mqueue rw,nosuid,nodev,noexec,relatime shared:15 - mqueue mqueue rw
36 21 0:7 / /sys/kernel/debug rw,nosuid,nodev,noexec,relatime shared:16 - debugfs debugfs rw
37 21 0:12 / /sys/kernel/tracing rw,nosuid,nodev,noexec,relatime shared:17 - tracefs tracefs rw
38 26 0:31 / /tmp rw,nosuid,nodev shared:18 - tmpfs tmpfs rw,inode64
39 25 0:32 / /run/rpc_pipefs rw,relatime shared:19 - rpc_pipefs sunrpc rw
40 22 0:33 / /proc/fs/nfsd rw,relatime shared:20 - nfsd nfsd rw
41 21 0:34 / /sys/fs/fuse/connections rw,nosuid,nodev,noexec,relatime shared:21 - fusectl fusectl rw
42 21 0:35 / /sys/kernel/config rw,nosuid,nodev,noexec,relatime shared:22 - configfs configfs rw
279 33 0:49 / /proc/sys/fs/binfmt_misc rw,nosuid,nodev,noexec,relatime shared:154 - binfmt_misc binfmt_misc rw
285 26 0:50 / /boot/grub rw,relatime shared:157 - zfs boot-pool/grub rw,xattr,noacl
292 26 0:51 / /mnt/dozer rw,noatime shared:161 - zfs dozer rw,xattr,posixacl
355 292 0:62 / /mnt/dozer/posixacltest rw,noatime shared:197 - zfs dozer/posixacltest rw,xattr,posixacl
397 355 0:66 / /mnt/dozer/posixacltest/foo rw,noatime shared:221 - zfs dozer/posixacltest/foo rw,xattr,posixacl
334 292 0:59 / /mnt/dozer/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa rw,noatime shared:185 - zfs dozer/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa rw,xattr,posixacl
383 334 0:65 / /mnt/dozer/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb rw,noatime shared:213 - zfs dozer/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb rw,xattr,posixacl
418 383 0:69 / /mnt/dozer/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/cccccccccccccccccccccccccccccccccccccccccccccc rw,noatime shared:233 - zfs dozer/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/cccccccccccccccccccccccccccccccccccccccccccccc rw,xattr,posixacl
439 334 0:72 / /mnt/dozer/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/fdd rw,noatime shared:245 - zfs dozer/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/fdd rw,xattr,posixacl
313 292 0:54 / /mnt/dozer/RO ro,nosuid,noexec,noatime shared:173 - zfs dozer/RO ro,xattr,posixacl
320 292 0:57 / /mnt/dozer/TESTSMB rw,noatime shared:177 - zfs dozer/TESTSMB rw,xattr,nfs4acl
299 292 0:52 / /mnt/dozer/NFS4 rw shared:165 - zfs dozer/NFS4 rw,xattr,nfs4acl
411 299 0:67 / /mnt/dozer/NFS4/stuff rw shared:229 - zfs dozer/NFS4/stuff rw,xattr,nfs4acl
390 292 0:64 / /mnt/dozer/test_homes rw,noatime shared:217 - zfs dozer/test_homes rw,xattr,nfs4acl
341 292 0:55 / /mnt/dozer/SMB rw,noatime shared:189 - zfs dozer/SMB rw,xattr,nfs4acl
425 341 0:70 / /mnt/dozer/SMB/SUBDATASET rw,noatime shared:237 - zfs dozer/SMB/SUBDATASET rw,xattr,nfs4acl
348 292 0:58 / /mnt/dozer/TESTNFS rw,noatime shared:193 - zfs dozer/TESTNFS rw,xattr,posixacl
376 292 0:63 / /mnt/dozer/smb-vss rw,noatime shared:209 - zfs dozer/smb-vss rw,xattr,nfs4acl
432 376 0:71 / /mnt/dozer/smb-vss/sub1 rw,noatime shared:241 - zfs dozer/smb-vss/sub1 rw,xattr,nfs4acl
327 292 0:56 / /mnt/dozer/TESTFUN rw,noatime shared:181 - zfs dozer/TESTFUN rw,xattr,noacl
369 292 0:61 / /mnt/dozer/administrative_share rw,noatime shared:205 - zfs dozer/administrative_share rw,xattr,posixacl
404 369 0:68 / /mnt/dozer/administrative_share/backups_dataset rw,noatime shared:225 - zfs dozer/administrative_share/backups_dataset rw,xattr,posixacl
446 404 0:73 / /mnt/dozer/administrative_share/backups_dataset/userdata rw,noatime shared:249 - zfs dozer/administrative_share/backups_dataset/userdata rw,xattr,posixacl
453 446 0:74 / /mnt/dozer/administrative_share/backups_dataset/userdata/DOMAIN_GOAT rw,noatime shared:253 - zfs dozer/administrative_share/backups_dataset/userdata/DOMAIN_GOAT rw,xattr,posixacl
460 453 0:75 / /mnt/dozer/administrative_share/backups_dataset/userdata/DOMAIN_GOAT/bob rw,noatime shared:257 - zfs dozer/administrative_share/backups_dataset/userdata/DOMAIN_GOAT/bob rw,xattr,posixacl
306 292 0:53 / /mnt/dozer/EXPORT rw,noatime shared:169 - zfs dozer/EXPORT rw,xattr,posixacl
362 292 0:60 / /mnt/dozer/noacl rw,noatime shared:201 - zfs dozer/noacl rw,xattr,noacl
93 26 0:38 / /var/db/system rw,relatime shared:48 - zfs dozer/.system rw,xattr,noacl
100 93 0:39 / /var/db/system/cores rw,relatime shared:52 - zfs dozer/.system/cores rw,xattr,noacl
107 93 0:40 / /var/db/system/samba4 rw,relatime shared:56 - zfs dozer/.system/samba4 rw,xattr,noacl
121 93 0:42 / /var/db/system/rrd-f803551cf3cd4df8a1ddb0569466b72a rw,relatime shared:64 - zfs dozer/.system/rrd-f803551cf3cd4df8a1ddb0569466b72a rw,xattr,noacl
151 93 0:43 / /var/db/system/configs-f803551cf3cd4df8a1ddb0569466b72a rw,relatime shared:68 - zfs dozer/.system/configs-f803551cf3cd4df8a1ddb0569466b72a rw,xattr,noacl
158 93 0:44 / /var/db/system/webui rw,relatime shared:100 - zfs dozer/.system/webui rw,xattr,noacl
187 93 0:45 / /var/db/system/services rw,relatime shared:104 - zfs dozer/.system/services rw,xattr,noacl
234 93 0:46 / /var/db/system/glusterd rw,relatime shared:143 - zfs dozer/.system/glusterd rw,xattr,noacl
241 93 0:47 / /var/db/system/ctdb_shared_vol rw,relatime shared:147 - zfs dozer/.system/ctdb_shared_vol rw,xattr,noacl
271 26 0:39 / /var/lib/systemd/coredump rw,relatime shared:52 - zfs dozer/.system/cores rw,xattr,noacl
467 26 0:76 / /mnt/tank\040space\040 rw,noatime shared:261 - zfs tank\040space\040 rw,xattr,posixacl
474 467 0:77 / /mnt/tank\040space\040/Dataset\040With\040a\040space rw,noatime shared:265 - zfs tank\040space\040/Dataset\040With\040a\040space rw,xattr,posixacl
572 26 0:1005 / /mnt/zz rw,noatime shared:4257 - zfs zz rw,xattr,posixacl,casesensitive
7460 572 0:1005 / /mnt/zz/ds920 rw,noatime shared:4257 - zfs zz/ds920 rw,xattr,posixacl,casesensitive
8069 572 0:1214 / /mnt/zz/mixy rw,noatime shared:4507 - zfs zz/mixy rw,xattr,posixacl,casemixed
537 327 0:75 / /mnt/dozer/TESTFUN/mp29-nfs0016K ro shared:301 - zfs dozer/TESTFUN/mp29-nfs0016K ro,xattr,posixacl,casesensitive
"""


def test__mntinfo_spaces():
    line = r'474 467 0:77 / /mnt/tank\040space\040/Dataset\040With\040a\040space rw,noatime shared:265 - zfs tank\040space\040/Dataset\040With\040a\040space rw,xattr,posixacl'
    data = {}
    __parse_to_mnt_id(line, data)
    assert 474 in data
    mntent = data[474]
    assert mntent['mount_id'] == 474
    assert mntent['parent_id'] == 467
    assert mntent['device_id'] == {'major': 0, 'minor': 77, 'dev_t': 77}
    assert mntent['root'] == '/'
    assert mntent['mountpoint'] == '/mnt/tank space /Dataset With a space'
    assert mntent['mount_opts'] == ['RW', 'NOATIME']
    assert mntent['fs_type'] == 'zfs'
    assert mntent['mount_source'] == 'tank space /Dataset With a space'
    assert mntent['super_opts'] == ['RW', 'XATTR', 'POSIXACL']


def test__mntinfo_dashes():
    line = r'868 842 0:85 / /mnt/stdpool-backup/stdpool-0/shares/--- ro,noatime shared:448 - zfs stdpool-backup/stdpool-0/shares/--- ro,xattr,posixacl,caseinsensitive'  # noqa
    data = {}
    __parse_to_mnt_id(line, data)
    assert 868 in data
    mntent = data[868]
    assert mntent['mount_id'] == 868
    assert mntent['parent_id'] == 842
    assert mntent['device_id'] == {'major': 0, 'minor': 85, 'dev_t': 85}
    assert mntent['root'] == '/'
    assert mntent['mountpoint'] == '/mnt/stdpool-backup/stdpool-0/shares/---'
    assert mntent['mount_opts'] == ['RO', 'NOATIME']
    assert mntent['fs_type'] == 'zfs'
    assert mntent['mount_source'] == 'stdpool-backup/stdpool-0/shares/---'
    assert mntent['super_opts'] == ['RO', 'XATTR', 'POSIXACL', 'CASEINSENSITIVE']


def test__getmntinfo():
    def __rebuild_device_info(e):
        return f'{e["mount_id"]} {e["parent_id"]} {e["device_id"]["major"]}:{e["device_id"]["minor"]} {e["root"]}'

    def __rebuild_opts(e):
        mnt_opts = ','.join([x.lower() for x in e['mount_opts']])
        sb_opts = ','.join([x.lower() for x in e['super_opts']])
        return mnt_opts, sb_opts

    for line in fake_mntinfo.splitlines():
        data = {}
        __parse_to_mnt_id(line, data)

        mnt_data = list(data.values())[0]
        assert __rebuild_device_info(mnt_data) in line
        for opt in __rebuild_opts(mnt_data):
            assert opt.casefold() in line.casefold()

        assert mnt_data['mountpoint'] in line.replace('\\040', ' ')
        assert mnt_data['mount_source'] in line.replace('\\040', ' ')
        assert mnt_data['fs_type'] in line


def test__atime_and_casesentivity_in_mntinfo():
    line = r'7460 572 0:1005 / /mnt/zz/ds920 rw,noatime shared:4257 - zfs zz/ds920 rw,xattr,posixacl,casesensitive'
    data = {}
    __parse_to_mnt_id(line, data)
    assert 7460 in data
    mntent = data[7460]
    assert 'NOATIME' in mntent['mount_opts']
    assert 'CASESENSITIVE' in mntent['super_opts']

    line = r'8069 306 0:1214 / /mnt/zz/mixy rw,noatime shared:4507 - zfs zz/mixy rw,xattr,posixacl,casemixed'
    data = {}
    __parse_to_mnt_id(line, data)
    assert 8069 in data
    mntent = data[8069]
    assert 'CASEMIXED' in mntent['super_opts']


def test__readonly_in_mntinfo():
    line = r'537 327 0:75 / /mnt/dozer/TESTFUN/mp29-nfs0016K ro shared:301 - zfs dozer/TESTFUN/mp29-nfs0016K ro,xattr,posixacl,casesensitive'
    data = {}
    __parse_to_mnt_id(line, data)
    assert 537 in data
    assert 'RO' in data[537]['mount_opts']


def test__mount_id_key():
    line = r'537 327 0:75 / /mnt/tank/perf/mp29-nfs0016K ro shared:301 - zfs tank/perf/mp29-nfs0016K ro,xattr,posixacl,casesensitive'
    data = {}
    __parse_to_mnt_id(line, data)
    assert 537 in data


def test__mountinfo_tree():
    data = {}
    for line in fake_mntinfo.splitlines():
        __parse_to_mnt_id(line, data)

    root = __create_tree(data, 369)
    assert root['mount_source'] == 'dozer/administrative_share', str(root)
    assert len(root['children']) == 1, str(root)

    root = root['children'][0]
    assert root['mount_source'] == 'dozer/administrative_share/backups_dataset'
    assert len(root['children']) == 1, str(root)

    root = root['children'][0]
    assert root['mount_source'] == 'dozer/administrative_share/backups_dataset/userdata'
    assert len(root['children']) == 1, str(root)

    root = root['children'][0]
    assert root['mount_source'] == 'dozer/administrative_share/backups_dataset/userdata/DOMAIN_GOAT'
    assert len(root['children']) == 1, str(root)

    root = root['children'][0]
    assert root['mount_source'] == 'dozer/administrative_share/backups_dataset/userdata/DOMAIN_GOAT/bob'
    assert len(root['children']) == 0, str(root)


def test__mountinfo_tree_miss():
    data = {}
    for line in fake_mntinfo.splitlines():
        __parse_to_mnt_id(line, data)

    with pytest.raises(KeyError):
        __create_tree(data, 8675309)


def test__mountinfo_missing_optional_fields():
    line = r'282 213 0:47 / / rw,relatime - overlay overlay rw,lowerdir=/var/lib/docker/overlay2/l/5L3KSV23NGJN7OAT6JAPAPESIH:/var/lib/docker/overlay2/l/TDVGJBW7AOL4CADLI72HXRISIC,upperdir=/var/lib/docker/overlay2/3815fd731d8026048c8097461cb66cc11b1390337a3447315fd1c8e402f2c4a4/diff,workdir=/var/lib/docker/overlay2/3815fd731d8026048c8097461cb66cc11b1390337a3447315fd1c8e402f2c4a4/work,nouserxattr'  # noqa
    # Verify that this does not raise an index erro due to missing optional fields
    __mntent_dict(line)
