#!/usr/bin/env python2.7
#+
# Copyright 2015 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################


import os
import json
from dsl import load_file
from utils import e, sh, sh_str, readfile, setfile, template, setup_env


dsl = load_file('${BUILD_CONFIG}/release.pyd', os.environ)
url = dsl['url']


def stage_release():
    sh('mkdir -p ${RELEASE_STAGEDIR}/${BUILD_ARCH_SHORT}')
    for ext in dsl['format']:
        path = e('${OBJDIR}/${NAME}.${ext}')
        if os.path.exists(path):
            sh('mv ${path} ${RELEASE_STAGEDIR}/${BUILD_ARCH_SHORT}/')
            sh('mv ${path}.sha256 ${RELEASE_STAGEDIR}/${BUILD_ARCH_SHORT}/')


def get_aux_files_desc():
    for name, aux in dsl['aux_file'].items():
        yield {
            'filename': name,
            'hash': sh_str("sha256 -q ${RELEASE_STAGEDIR}/${name}"),
        }


def get_image_files_desc():
    for ext in dsl['format']:
        path = e('${RELEASE_STAGEDIR}/${BUILD_ARCH_SHORT}/${NAME}.${ext}')
        filename = os.path.basename(path)
        if os.path.exists(path):
            yield {
                'filename': filename,
                'type': ext,
                'hash': sh_str("sha256 -q ${path}"),
                'url': e("${url}/${filename}")
            }


def create_aux_files(dsl, dest):
    for name, aux in dsl['aux_file'].items():
        if not os.path.exists(aux['source']):
            continue

        if aux.get('template'):
            f = template(aux['source'])
        else:
            f = readfile(aux['source'])

        setfile('${dest}/${name}', f)


def create_json():
    version = e('${VERSION}').split('-')[0]
    build_type = e('${VERSION}').split('-')[1]
    json_file = {
        'name': e('${PRODUCT}'),
        'version': e('${version}'),
        'type': e('${build_type}'),
        'date': e('${BUILD_TIMESTAMP}'),
        'aux_files': list(get_aux_files_desc()),
        'arch': {
            e('${BUILD_ARCH}'): list(get_image_files_desc())
        }
    }

    f = open(e("${RELEASE_STAGEDIR}/CHECKSUMS.json"), 'a')
    json.dump(json_file, f, indent=4)
    f.close()


if __name__ == '__main__':
    stage_release()
    create_aux_files(dsl, e('${RELEASE_STAGEDIR}'))
    create_json()
