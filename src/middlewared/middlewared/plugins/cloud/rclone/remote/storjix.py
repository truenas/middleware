from __future__ import annotations

import errno
import io
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import boto3
import botocore
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
import requests

from middlewared.api.current import StorjIxCredentialsModel
from middlewared.plugins.cloud.rclone.base import BaseRcloneRemote
from middlewared.service_exception import CallError
from middlewared.utils.network import INTERNET_TIMEOUT

if TYPE_CHECKING:
    from middlewared.api.current import CloudTaskAttributes


class StorjIxError(CallError):
    pass


class StorjIxRcloneRemote(BaseRcloneRemote[StorjIxCredentialsModel]):
    credentials_schema = StorjIxCredentialsModel

    name = "STORJ_IX"
    title = "Storj"

    buckets = True
    can_create_bucket = True
    custom_list_buckets = True

    fast_list = True

    rclone_type = "s3"

    def create_bucket(self, credentials: StorjIxCredentialsModel, name: str) -> None:
        s3_client = boto3.client(
            "s3",
            config=botocore.config.Config(user_agent="ix-storj-1"),
            endpoint_url=str(credentials.endpoint),
            aws_access_key_id=credentials.access_key_id.get_secret_value(),
            aws_secret_access_key=credentials.secret_access_key.get_secret_value(),
        )
        # s3 bucket naming rules: https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html
        try:
            s3_client.create_bucket(Bucket=name)
        except s3_client.exceptions.BucketAlreadyExists as e:
            raise CallError(str(e), errno=errno.EEXIST)
        except botocore.exceptions.ParamValidationError as e:
            raise StorjIxError(
                "The bucket name can only contain lowercase letters, numbers, and hyphens.", errno.EINVAL, str(e)
            )
        except botocore.exceptions.ClientError as e:
            if "InvalidBucketName" in e.args[0]:
                raise StorjIxError(
                    "The bucket name must be between 3-63 characters in length and cannot contain uppercase.",
                    errno.EINVAL,
                    str(e),
                )
            raise

    def list_buckets(self, credentials: StorjIxCredentialsModel) -> list[Any]:
        endpoint = credentials.endpoint
        url = f"{endpoint}?attribution"

        creds = Credentials(
            credentials.access_key_id.get_secret_value(),
            credentials.secret_access_key.get_secret_value(),
        )
        request = AWSRequest(method="GET", url=url)
        SigV4Auth(creds, "s3", "").add_auth(request)

        r = requests.get(url, headers=dict(request.headers), timeout=INTERNET_TIMEOUT)
        r.raise_for_status()

        ns = "{http://s3.amazonaws.com/doc/2006-03-01/}"

        def text(bucket: ET.Element, tag: str) -> str | None:
            if (element := bucket.find(f"{ns}{tag}")) is not None:
                return element.text
            return None

        return [
            {
                "name": text(bucket, "Name"),
                "time": text(bucket, "CreationDate"),
                "enabled": "ix-storj-1" in (text(bucket, "Attribution") or ""),
            }
            for bucket in ET.parse(io.StringIO(r.text)).iter(f"{ns}Bucket")
        ]

    def get_credentials_extra(self, credentials: StorjIxCredentialsModel) -> dict[str, Any]:
        return {"endpoint": credentials.endpoint, "provider": "Other"}

    def get_task_extra(self, attributes: CloudTaskAttributes, credentials: StorjIxCredentialsModel) -> dict[str, Any]:
        # Storj recommended these settings
        return {
            "chunk_size": "64M",
            "disable_http2": "true",
            "upload_cutoff": "64M",
        }

    def get_restic_config(
        self,
        attributes: CloudTaskAttributes,
        credentials: StorjIxCredentialsModel,
    ) -> tuple[str, dict[str, str]]:
        env = {
            "AWS_ACCESS_KEY_ID": credentials.access_key_id.get_secret_value(),
            "AWS_SECRET_ACCESS_KEY": credentials.secret_access_key.get_secret_value(),
        }
        return urlparse(str(credentials.endpoint)).hostname or "", env
