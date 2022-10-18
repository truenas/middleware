import errno
import io
import xml.etree.ElementTree as ET

from aws_requests_auth.aws_auth import AWSRequestsAuth
import boto3
import botocore
import requests

from middlewared.rclone.base import BaseRcloneRemote
from middlewared.schema import Str
from middlewared.service_exception import CallError
from middlewared.utils.network import INTERNET_TIMEOUT


class StorjIxRcloneRemote(BaseRcloneRemote):
    name = "STORJ_IX"
    title = "Storj iX"

    buckets = True
    can_create_bucket = True
    custom_list_buckets = True

    fast_list = True

    rclone_type = "s3"

    credentials_schema = [
        Str("access_key_id", title="Access Key ID", required=True),
        Str("secret_access_key", title="Secret Access Key", required=True),
    ]

    task_schema = []

    async def create_bucket(self, credentials, name):
        def create_bucket_sync():
            s3_client = boto3.client(
                "s3",
                config=botocore.config.Config(user_agent="ix-storj-1"),
                endpoint_url="https://gateway.storjshare.io",
                aws_access_key_id=credentials["attributes"]["access_key_id"],
                aws_secret_access_key=credentials["attributes"]["secret_access_key"],
            )
            try:
                s3_client.create_bucket(Bucket=name)
            except s3_client.exceptions.BucketAlreadyExists as e:
                raise CallError(str(e), errno=errno.EEXIST)

        return await self.middleware.run_in_thread(create_bucket_sync)

    async def list_buckets(self, credentials):
        def list_buckets_sync():
            auth = AWSRequestsAuth(aws_access_key=credentials["attributes"]["access_key_id"],
                                   aws_secret_access_key=credentials["attributes"]["secret_access_key"],
                                   aws_host="gateway.storjshare.io",
                                   aws_region="",
                                   aws_service="s3")

            r = requests.get("https://gateway.storjshare.io/?attribution", auth=auth, timeout=INTERNET_TIMEOUT)
            r.raise_for_status()

            ns = "{http://s3.amazonaws.com/doc/2006-03-01/}"
            return [
                {
                    "name": bucket.find(f"{ns}Name").text,
                    "time": bucket.find(f"{ns}CreationDate").text,
                    "enabled": "ix-storj-1" in bucket.find(f"{ns}Attribution").text,
                }
                for bucket in ET.parse(io.StringIO(r.text)).iter(f"{ns}Bucket")
            ]

        return await self.middleware.run_in_thread(list_buckets_sync)

    async def get_credentials_extra(self, credentials):
        return {"endpoint": "https://gateway.storjshare.io"}

    async def get_task_extra(self, task):
        # Storj recommended these settings
        return {
            "chunk_size": "64M",
            "upload_cutoff": "64M",
        }
