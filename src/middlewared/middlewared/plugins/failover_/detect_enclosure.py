# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.service import Service

from .detect_utils import detect_platform


class EnclosureDetectionService(Service):

    class Config:
        namespace = 'failover.enclosure'
        private = True

    def detect(self):
        return detect_platform()
