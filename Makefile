.if exists(build/hooks/Makefile)
.include "build/hooks/Makefile"
.endif

LABEL ?= FreeNAS
VERSION ?= 10.1-M1
TRAIN ?= ${NANO_LABEL}-10-Nightlies
BUILD_TIMESTAMP != date '+%Y%m%d'
BUILD_STARTED != date '+%s'
COMPANY ?= "iXsystems"
STAGEDIR = "${NANO_LABEL}-${VERSION}-${BUILD_TIMESTAMP}"
IX_INTERNAL_PATH = "/freenas/Dev/releng/${NANO_LABEL}/nightlies/"
BUILD_DEBUG=yes

BUILD_ROOT != pwd
BUILD_CONFIG := ${BUILD_ROOT}/build/config
BUILD_TOOLS := ${BUILD_TOOLS}/build/tools
PYTHONPATH := ${BUILD_ROOT}/build/lib

MAKEOBJDIRPREFIX := ${BUILD_ROOT}/objs/os-base/amd64

.ifdef SCRIPT
RELEASE_LOGFILE?=${SCRIPT}
.else
RELEASE_LOGFILE?=release.build.log
.endif

GIT_REPO_SETTING=.git-repo-setting
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

.if defined(NANO_ARCH)
.export NANO_ARCH
.endif

.if defined(CHANGELOG)
.export CHANGELOG
.endif

all:	check-root build

.BEGIN:
.if !make(remote) && !make(sync)
	@build/tools/check-host.py
.if !make(checkout) && !make(update) && !make(clean) && !make(distclean) && !make(git-internal) && !make(git-external)
	@build/tools/check-sandbox.py
.endif
.endif

check-root:
	@[ `id -u` -eq 0 ] || ( echo "Sorry, you must be running as root to build this."; exit 1 )

build: git-verify portsjail ports
	@build/tools/build.py

checkout: git-verify
	@build/tools/checkout.py

update: git-verify
	git pull
	build/do_checkout.sh

clean:
	build/build_cleanup.py
	rm -rf ${NANO_LABEL}-${VERSION}-* release.build.log
	rm -rf objs os-base

clean-packages:
	find objs/os-base/*/ports -type f -delete

clean-package:
.if defined(p)
	find objs/os-base/*/ports -name "${p}*" | xargs rm -fr
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
	${MAKE} clean-package p=freenas-10gui
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
	script -a ${RELEASE_LOGFILE} ${MAKE} build
	script -a ${RELEASE_LOGFILE} build/create_release_distribution.sh
	script -a ${RELEASE_LOGFILE} build/create_upgrade_distribution.sh

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
	sh -x build/create_iso.sh

# intentionally split up to prevent abuse/spam
BUILD_BUG_DOMAIN?=ixsystems.com
BUILD_BUG_USER?=build-bugs
BUILD_BUG_EMAIL?=${BUILD_BUG_USER}@${BUILD_BUG_DOMAIN}

build-bug-report:
	mail -s "build fail for $${SUDO_USER:-$$USER}" ${BUILD_BUG_EMAIL} < \
		${RELEASE_LOGFILE}

git-verify:
	@if [ ! -f ${GIT_REPO_SETTING} ]; then \
		echo "No git repo choice is set.  Please use \"make git-external\" to build as an"; \
		echo "external developer or \"make git-internal\" to build as an ${COMPANY}"; \
		echo "internal developer.  You only need to do this once."; \
		exit 1; \
	fi
	@echo "NOTICE: You are building from the ${GIT_LOCATION} git repo."

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
	build/ports/build-gui.sh

ports: check-root build-gui
	build/ports/create-poudriere-conf.sh
	build/ports/create-poudriere-make.conf.sh
	build/ports/prepare-jail.sh
	build/ports/fetch-ports-srcs.sh
	build/ports/create-ports-list.sh
	build/ports/build-ports.sh

portsjail:
	@build/tools/build-os.py
	@build/tools/install-jail.py
