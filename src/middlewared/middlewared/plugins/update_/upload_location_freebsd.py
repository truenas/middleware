# -*- coding=utf-8 -*-
import os
import shutil
import subprocess

from bsd import geom

from middlewared.service import CallError, private, Service

from .utils import UPLOAD_LOCATION

UPLOAD_LABEL = 'updatemdu'


class UpdateService(Service):
    @private
    def create_upload_location(self):
        geom.scan()
        klass_label = geom.class_by_name('LABEL')
        prov = klass_label.xml.find(
            f'.//provider[name = "label/{UPLOAD_LABEL}"]/../consumer/provider'
        )
        if prov is None:
            cp = subprocess.run(
                ['mdconfig', '-a', '-t', 'swap', '-s', '2800m'],
                text=True, capture_output=True, check=False,
            )
            if cp.returncode != 0:
                raise CallError(f'Could not create memory device: {cp.stderr}')
            mddev = cp.stdout.strip()

            subprocess.run(['glabel', 'create', UPLOAD_LABEL, mddev], capture_output=True, check=False)

            cp = subprocess.run(
                ['newfs', f'/dev/label/{UPLOAD_LABEL}'],
                text=True, capture_output=True, check=False,
            )
            if cp.returncode != 0:
                raise CallError(f'Could not create temporary filesystem: {cp.stderr}')

            shutil.rmtree(UPLOAD_LOCATION, ignore_errors=True)
            os.makedirs(UPLOAD_LOCATION)

            cp = subprocess.run(
                ['mount', f'/dev/label/{UPLOAD_LABEL}', UPLOAD_LOCATION],
                text=True, capture_output=True, check=False,
            )
            if cp.returncode != 0:
                raise CallError(f'Could not mount temporary filesystem: {cp.stderr}')

        shutil.chown(UPLOAD_LOCATION, 'www', 'www')
        os.chmod(UPLOAD_LOCATION, 0o755)
        return UPLOAD_LOCATION

    @private
    def destroy_upload_location(self):
        geom.scan()
        klass_label = geom.class_by_name('LABEL')
        prov = klass_label.xml.find(
            f'.//provider[name = "label/{UPLOAD_LABEL}"]/../consumer/provider'
        )
        if prov is None:
            return
        klass_md = geom.class_by_name('MD')
        prov = klass_md.xml.find(f'.//provider[@id = "{prov.attrib["ref"]}"]/name')
        if prov is None:
            return

        mddev = prov.text

        subprocess.run(
            ['umount', UPLOAD_LOCATION], capture_output=True, check=False,
        )
        cp = subprocess.run(
            ['mdconfig', '-d', '-u', mddev],
            text=True, capture_output=True, check=False,
        )
        if cp.returncode != 0:
            raise CallError(f'Could not destroy memory device: {cp.stderr}')
