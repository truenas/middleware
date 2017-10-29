from freenasUI.middleware.client import client
from lockfile import locked
import os
import json

DW_PROGRESS = '/tmp/.vm_container_download'

def vm_enabled():
    with client as c:
        flags = c.call('vm.flags')
        if flags.get('intel_vmx'):
            return True
        elif flags.get('amd_rvi'):
            return True
        else:
            return False

@locked(DW_PROGRESS)
def dump_download_progress(data):
    with open(DW_PROGRESS, 'w') as dw_f:
            details_msg = 'Lets start the magic...'
            progress_n = data.get('progress').get('percent')
            if progress_n:
                if progress_n <= 10:
                    details_msg = 'Start to download a prebuilt container image.'
                elif progress_n > 10 and progress_n <= 50:
                    details_msg = 'Almost done....'
                elif progress_n > 50 and progress_n <= 90:
                    details_msg = 'Downloading a prebuilt container image.'
                elif progress_n > 95:
                    details_msg = 'Preparing environment....'

            jdata = {
                'error': data.get('error'),
                'finished': data.get('state'),
                'percent': data.get('progress').get('percent'),
                'details': details_msg,
            }
            dw_f.write(json.dumps(jdata))

@locked(DW_PROGRESS)
def load_progress():
    if os.path.exists(DW_PROGRESS):
        with open(DW_PROGRESS, 'r') as f:
            data = json.loads(f.read())
            if data:
                return data
    return None
