from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import WebUIDatasetDetailsArgs, WebUIDatasetDetailsEntry, WebUIDatasetDetailsResult
from middlewared.service import Service

from .dataset_details import dataset_details

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App


class WebUIDatasetService(Service):
    class Config:
        namespace = "webui.dataset"
        cli_private = True

    @api_method(
        WebUIDatasetDetailsArgs,
        WebUIDatasetDetailsResult,
        roles=["DATASET_READ"],
        pass_app=True,
        pass_app_require=True,
        check_annotations=True,
    )
    def details(self, app: App) -> list[WebUIDatasetDetailsEntry]:
        """
        Return every dataset with the shares, virtual machines, containers, apps and data protection tasks that use
        it.

        This method is designed for the Datasets page of the web interface and is not a general purpose API. Use
        :method:`zfs.resource.list`, :method:`zfs.resource.snapshot.count` and :method:`zfs.resource.attachments` for
        programmatic access.

        Each consumer list, task count and the snapshot count is ``null`` when the caller is not authorized to call
        the method it comes from, for example :method:`sharing.smb.query` for SMB shares.
        """
        return dataset_details(self.context, app)
