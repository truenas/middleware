#!/usr/local/bin/python3
#
# Copyright (c) 2018 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.
#
# Redmine 32763

import sys
sys.path.append('/usr/local/www')
from freenasUI.support.utils import get_license

def main():
    license, error = get_license()
    if license is None or not license.system_serial_ha:
        print('False')
    print('True')

if __name__ == '__main__':
    main()
