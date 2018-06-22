#!/usr/bin/env python3.6

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE

import shutil
import subprocess
import time
import urllib.parse

DATASET = "data/import"
DATASET_PATH = os.path.join("/mnt", DATASET)

IMAGES = {}


def setup_function():
    DELETE(f"/pool/dataset/id/{urllib.parse.quote(DATASET, '')}/")

    result = POST("/pool/dataset", {"name": DATASET})
    assert result.status_code == 200, result.text

    for image in ["msdosfs", "msdosfs-nonascii", "ntfs"]:
        shutil.copy(os.path.join(os.path.dirname(__file__), "fixtures", f"{image}.gz"), f"/tmp/{image}.gz")
        subprocess.check_call(["gunzip", "-f", f"/tmp/{image}.gz"])

        IMAGES[image] = subprocess.check_output(
            ["mdconfig", "-a", "-t", "vnode", "-f", f"/tmp/{image}"], encoding="utf8").strip()


def teardown_function():
    for md in IMAGES.values():
        subprocess.check_call(["mdconfig", "-d", "-u", md])

    DELETE(f"/pool/dataset/id/{urllib.parse.quote(DATASET, '')}/")


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


def test_01_import_msdosfs():
    result = POST("/pool/import_disk", {
        "volume": f"/dev/{IMAGES['msdosfs']}s1",
        "fs_type": "msdosfs",
        "fs_options": {},
        "dst_path": DATASET_PATH,
    })
    assert result.status_code == 200, result.text

    job_id = result.json()

    expect_state(job_id, "SUCCESS")

    assert os.path.exists(os.path.join(DATASET_PATH, "Directory/File"))


def test_02_import_nonascii_msdosfs_fails():
    result = POST("/pool/import_disk", {
        "volume": f"/dev/{IMAGES['msdosfs-nonascii']}s1",
        "fs_type": "msdosfs",
        "fs_options": {},
        "dst_path": DATASET_PATH,
    })
    assert result.status_code == 200, result.text

    job_id = result.json()

    job = expect_state(job_id, "FAILED")

    assert job["error"] == "rsync failed with exit code 23", job
    assert os.path.exists(os.path.join(DATASET_PATH, "Directory/File"))


def test_03_import_nonascii_msdosfs():
    result = POST("/pool/import_disk", {
        "volume": f"/dev/{IMAGES['msdosfs-nonascii']}s1",
        "fs_type": "msdosfs",
        "fs_options": {"locale": "ru_RU.UTF-8"},
        "dst_path": DATASET_PATH,
    })
    assert result.status_code == 200, result.text

    job_id = result.json()

    expect_state(job_id, "SUCCESS")

    assert os.path.exists(os.path.join(DATASET_PATH, "Каталог/Файл"))


def test_04_import_ntfs():
    result = POST("/pool/import_disk", {
        "volume": f"/dev/{IMAGES['ntfs']}s1",
        "fs_type": "ntfs",
        "fs_options": {},
        "dst_path": DATASET_PATH,
    })
    assert result.status_code == 200, result.text

    job_id = result.json()

    expect_state(job_id, "SUCCESS")

    assert os.path.exists(os.path.join(DATASET_PATH, "Каталог/Файл"))
