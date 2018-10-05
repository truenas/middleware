#!/usr/bin/env python3.6

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, DELETE, SSH_TEST, send_file
from auto_config import ip, user, password

import time
import urllib.parse

DATASET = "tank/import"
urlDataset = "tank%2Fnfs"
DATASET_PATH = os.path.join("/mnt", DATASET)

IMAGES = {}


def expect_state(job_id, state):
    for _ in range(60):
        job = GET(f"/core/get_jobs/?id={job_id}").json()[0]

        if job["state"] in ["WAITING", "RUNNING"]:
            time.sleep(1)
            continue

        if job["state"] == state:
            return job
        else:
            assert False, job

    assert False, job


def test_01_setup_function():
    DELETE(f"/pool/dataset/id/{urlDataset}/")

    result = POST("/pool/dataset/", {"name": DATASET})
    assert result.status_code == 200, result.text

    for image in ["msdosfs", "msdosfs-nonascii", "ntfs"]:
        zf = os.path.join(os.path.dirname(__file__), "fixtures", f"{image}.gz")
        destination = f"/tmp/{image}.gz"

        assert send_file(zf, destination, user, None, ip)['result'] is True

        cmd = f"gunzip -f /tmp/{image}.gz"
        SSH_TEST(cmd, user, password, ip)

        cmd = f"mdconfig -a -t vnode -f /tmp/{image}"
        IMAGES[image] = SSH_TEST(cmd, user, password, ip)['output'].strip()


def test_02_import_msdosfs():
    result = POST("/pool/import_disk/", {
        "volume": f"/dev/{IMAGES['msdosfs']}s1",
        "fs_type": "msdosfs",
        "fs_options": {},
        "dst_path": DATASET_PATH,
    })
    assert result.status_code == 200, result.text

    job_id = result.json()

    expect_state(job_id, "SUCCESS")

    # assert os.path.exists(os.path.join(DATASET_PATH, "Directory/File"))


def test_03_import_nonascii_msdosfs_fails():
    result = POST("/pool/import_disk/", {
        "volume": f"/dev/{IMAGES['msdosfs-nonascii']}s1",
        "fs_type": "msdosfs",
        "fs_options": {},
        "dst_path": DATASET_PATH,
    })
    assert result.status_code == 200, result.text

    job_id = result.json()

    job = expect_state(job_id, "FAILED")

    assert job["error"] == "rsync failed with exit code 23", job
    # assert os.path.exists(os.path.join(DATASET_PATH, "Directory/File"))


def test_04_import_nonascii_msdosfs():
    result = POST("/pool/import_disk/", {
        "volume": f"/dev/{IMAGES['msdosfs-nonascii']}s1",
        "fs_type": "msdosfs",
        "fs_options": {"locale": "ru_RU.UTF-8"},
        "dst_path": DATASET_PATH,
    })
    assert result.status_code == 200, result.text

    job_id = result.json()

    expect_state(job_id, "SUCCESS")

    # assert os.path.exists(os.path.join(DATASET_PATH, "Каталог/Файл"))


def test_05_import_ntfs():
    result = POST("/pool/import_disk/", {
        "volume": f"/dev/{IMAGES['ntfs']}s1",
        "fs_type": "ntfs",
        "fs_options": {},
        "dst_path": DATASET_PATH,
    })
    assert result.status_code == 200, result.text

    job_id = result.json()

    expect_state(job_id, "SUCCESS")

    # assert os.path.exists(os.path.join(DATASET_PATH, "Каталог/Файл"))


def test_06_stop_md_and_delete_dataset():
    for md in IMAGES.values():
        cmd = f"mdconfig -d -u {md}"
        SSH_TEST(cmd, user, password, ip)
    DELETE(f"/pool/dataset/id/{urlDataset}/")
