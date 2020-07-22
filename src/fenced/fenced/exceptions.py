# Copyright (c) 2020 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.


class PanicExit(SystemExit):
    pass


class ExcludeDisksError(Exception):
    pass
