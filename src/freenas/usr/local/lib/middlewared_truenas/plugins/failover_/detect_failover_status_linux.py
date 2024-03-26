# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.service import private, Service


class DetectFailoverStatusService(Service):

    class Config:
        namespace = 'failover.status'

    @private
    async def get_local(self, app):

        # TODO
        # return SINGLE always on Linux until VRRP can be
        # implemented.

        return 'SINGLE'
