#-
# Copyright 2010-2015 iXsystems, Inc.
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

.if exists(build/hooks/Makefile)
.include "build/hooks/Makefile"
.endif

PRODUCT ?= FreeNAS
VERSION ?= 10.1-M1
BUILD_TIMESTAMP != date '+%Y%m%d'
BUILD_STARTED != date '+%s'
COMPANY ?= "iXsystems"
STAGEDIR = "${NANO_LABEL}-${VERSION}-${BUILD_TIMESTAMP}"
IX_INTERNAL_PATH = "/freenas/Dev/releng/${NANO_LABEL}/nightlies/"
BUILD_DEBUG=yes

BUILD_ROOT ?= ${.CURDIR}
BUILD_CONFIG := ${BUILD_ROOT}/build/config
BUILD_TOOLS := ${BUILD_ROOT}/build/tools
PYTHONPATH := ${BUILD_ROOT}/build/lib
MK := ${MAKE} SKIP_CHECKS=yes

MAKEOBJDIRPREFIX := ${BUILD_ROOT}/objs/os-base/amd64

.ifdef SCRIPT
RELEASE_LOGFILE?=${SCRIPT}
.else
RELEASE_LOGFILE?=release.build.log
.endif

GIT_REPO_SETTING=${BUILD_ROOT}/.git-repo-setting
.if exists(${GIT_REPO_SETTING})
GIT_LOCATION!=cat ${GIT_REPO_SETTING}
.endif
.export NANO_LABEL
.export VERSION
.export GIT_LOCATION
.export BUILD_TIMESTAMP
.export TRAIN
.export UPDATE_USER = sef	# For now, just use sef's account
.export DEBUG
.export BUILD_ROOT
.export BUILD_CONFIG
.export BUILD_TOOLS
.export PYTHONPATH
.export MAKEOBJDIRPREFIX
.export BUILD_STARTED

.if defined(NANO_ARCH)
.export NANO_ARCH
.endif

.if defined(CHANGELOG)
.export CHANGELOG
.endif

all:	check-root build

.BEGIN:
.ifndef SKIP_CHECKS
.if !make(remote) && !make(sync)
	@${BUILD_TOOLS}/check-host.py
.if !make(checkout) && !make(update) && !make(clean) && !make(distclean) && !make(git-internal) && !make(git-external)
	@${BUILD_TOOLS}/check-sandbox.py
.endif
.endif
.endif

check-root:
	@[ `id -u` -eq 0 ] || ( echo "Sorry, you must be running as root to build this."; exit 1 )

build: git-verify portsjail ports world packages images

world:
	@${BUILD_TOOLS}/install-world.py
	@${BUILD_TOOLS}/install-ports.py
	@${BUILD_TOOLS}/customize.py

packages:
	@${BUILD_TOOLS}/build-packages.py

checkout: git-verify
	@${BUILD_TOOLS}/checkout.py

update: git-verify
	git pull
	build/do_checkout.sh

dumpenv:
	@${BUILD_TOOLS}/dumpenv.py

clean:
	build/build_cleanup.py
	rm -rf ${NANO_LABEL}-${VERSION}-* release.build.log
	rm -rf objs os-base

clean-packages:
	find ${MAKEOBJDIRPREFIX}/ports -type f -delete

clean-package:
.if defined(p)
	find ${MAKEOBJDIRPREFIX}/ports -name "${p}*" | xargs rm -fr
.else
	@echo "Clean a single package from object tree"
	@echo "" 
	@echo "Usage:  ${MAKE} ${.TARGET} p=[package name]"
	@echo ""
	@echo "Examples:"
	@echo "        ${MAKE} ${.TARGET} p=freenas-ui"
	@echo "        ${MAKE} ${.TARGET} p=netatalk"
.endif

clean-ui-package:
	${MK} clean-package p=freenas-10gui
	rm -rf objs/os-base/*/gui-dest

distclean: clean
	rm -fr FreeBSD nas_source

save-build-env:
	build/save_build.sh

sync:
	rsync -al --info=progress2 \
		--rsync-path="sudo rsync" \
		--delete \
		--exclude '.git-repo-setting' \
		--exclude 'objs' \
		--exclude 'FreeBSD' \
		--exclude '.git' \
		--exclude '.idea' . ${host}:${dir}/

remote: sync
	ssh -o StrictHostKeyChecking=no -t ${host} sudo make -C ${dir} ${target}

reinstall-package:
	build/reinstall_package.sh ${host} ${p}

freenas: release
release: git-verify
	@if [ "${NANO_LABEL}" = "TrueNAS" -a "${GIT_LOCATION}" != "INTERNAL" ]; then echo "You can only run this target from an internal repository."; exit 2; fi
	@echo "Doing executing target $@ on host: `hostname`"
	@echo "Build directory: `pwd`"
	script -a ${RELEASE_LOGFILE} ${MK} build
	script -a ${RELEASE_LOGFILE} ${BUILD_TOOLS}/create-release-distribution.py
	script -a ${RELEASE_LOGFILE} ${BUILD_TOOLS}/create-upgrade-distribution.py

release-push: release
	/bin/sh build/post-to-upgrade.sh objs/LATEST/
	rm -rf "${IX_INTERNAL_PATH}/${STAGEDIR}"
	rm -rf "objs/${STAGEDIR}/FreeNAS-MANIFEST objs/${STAGEDIR}/Packages"
	cp ReleaseNotes "objs/${STAGEDIR}/"
	cp -r "objs/${STAGEDIR}" "${IX_INTERNAL_PATH}/${STAGEDIR}"
	if [ "${NANO_LABEL}" == "FreeNAS" ]; then \
		sh build/post-to-download.sh "${IX_INTERNAL_PATH}" "${NANO_LABEL}-${VERSION}" "${TRAIN}" "${BUILD_TIMESTAMP}"; \
	fi

update-push:	release
	/bin/sh build/post-to-upgrade.sh objs/LATEST/

rebuild: checkout all
	@sh build/create_release_distribution.sh

cdrom:
	@${BUILD_TOOLS}/create-iso.py

gui-upgrade:
	@${BUILD_TOOLS}/create-gui-upgrade.py

images: cdrom gui-upgrade

# intentionally split up to prevent abuse/spam
BUILD_BUG_DOMAIN?=ixsystems.com
BUILD_BUG_USER?=build-bugs
BUILD_BUG_EMAIL?=${BUILD_BUG_USER}@${BUILD_BUG_DOMAIN}

build-bug-report:
	mail -s "build fail for $${SUDO_USER:-$$USER}" ${BUILD_BUG_EMAIL} < \
		${RELEASE_LOGFILE}

.ifdef SKIP_CHECKS
git-verify:
	@if [ ! -f ${GIT_REPO_SETTING} ]; then \
		echo "No git repo choice is set.  Please use \"make git-external\" to build as an"; \
		echo "external developer or \"make git-internal\" to build as an ${COMPANY}"; \
		echo "internal developer.  You only need to do this once."; \
		exit 1; \
	fi
	@echo "NOTICE: You are building from the ${GIT_LOCATION} git repo."
.else:
git-verify:
	@
.endif


git-internal:
	@echo "INTERNAL" > ${GIT_REPO_SETTING}
	@echo "You are set up for internal (${COMPANY}) development.  You can use"
	@echo "the standard make targets (e.g. build or release) now."

git-external:
	@echo "EXTERNAL" > ${GIT_REPO_SETTING}
	@echo "You are set up for external (github) development.  You can use"
	@echo "the standard make targets (e.g. build or release) now."

tag:
	build/apply_tag.sh

build-gui: 
	@${BUILD_TOOLS}/build-gui.py

ports: check-root build-gui
	@${BUILD_TOOLS}/merge-pcbsd-ports.py
	@${BUILD_TOOLS}/build-ports.py

portsjail:
	@${BUILD_TOOLS}/build-os.py
	@${BUILD_TOOLS}/install-jail.py
