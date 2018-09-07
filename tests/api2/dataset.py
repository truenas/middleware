#!/usr/bin/env python3.6

# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, PUT
from auto_config import disk1, disk2


DATASET_NAME = 'tank%2Fdataset1'


def test_01_check_dataset_endpoint():
    assert isinstance(GET('/pool/dataset/').json(), list)


def test_02_create_dataset():
    result = POST(
        '/pool/dataset/', {
            'name': DATASET_NAME.replace('%2F', '/')
        }
    )
    assert result.status_code == 200, result.text


def test_03_query_dataset_by_name():
    dataset = GET(f'/pool/dataset/?id={DATASET_NAME}')

    assert isinstance(dataset.json()[0], dict)


def test_04_update_dataset_description():
    result = PUT(
        f'/pool/dataset/id/{DATASET_NAME}/', {
            'comments': 'testing dataset'
        }
    )

    assert result.status_code == 200, result.text


def test_05_set_permissions_for_dataset():
    result = POST(
        f'/pool/dataset/id/{DATASET_NAME}/permission/', {
            'acl': 'UNIX',
            'mode': '777',
            'group': 'nobody',
            'user': 'nobody'
        }
    )

    assert result.status_code == 200, result.text


def test_06_promoting_dataset():
    # TODO: ONCE WE HAVE MANUAL SNAPSHOT FUNCTIONAITY IN MIDDLEWARED,
    # THIS TEST CAN BE COMPLETED THEN
    pass


def test_07_delete_dataset():
    result = DELETE(
        f'/pool/dataset/id/{DATASET_NAME}/'
    )
    assert result.status_code == 200, result.text
