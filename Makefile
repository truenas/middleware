.if exists(build/hooks/Makefile)
.include "build/hooks/Makefile"
.endif

NANO_LABEL?=FreeNAS
VERSION?=9.3-MASTER
TRAIN?=${NANO_LABEL}-${VERSION}

.ifdef PRODUCTION
FREENAS_KEYFILE?=Keys/ix-freenas-key.key
.if !defined(_KEY)
KEY_PASSWORD!= build/read-password.sh
.endif
.else
FREENAS_KEYFILE?=Keys/ix-nightly-key.key
KEY_PASSWORD=""
.endif

COMPANY?="iXsystems"
.if !defined(BUILD_TIMESTAMP)
BUILD_TIMESTAMP!=date -u '+%Y%m%d%H%M'
PRINTABLE_TIMESTAMP!=date -u '+%Y/%m/%d-%H:%M'
.endif

STAGEDIR="${NANO_LABEL}-${VERSION}-${BUILD_TIMESTAMP}"
IX_INTERNAL_PATH="/freenas/Dev/releng/${NANO_LABEL}/nightlies/"
IX_STABLE_DIR="/freenas/Dev/releng/${NANO_LABEL}/9.3/STABLE/"

.ifdef SCRIPT
RELEASE_LOGFILE?=${SCRIPT}
.else
RELEASE_LOGFILE?=release.build.log
.endif


GIT_REPO_SETTING=.git-repo-setting
.if exists(${GIT_REPO_SETTING})
GIT_LOCATION!=cat ${GIT_REPO_SETTING}
.endif

ENV_SETUP=env _KEY=set

ENV_SETUP+= NANO_LABEL=${NANO_LABEL}
ENV_SETUP+= VERSION=${VERSION}
ENV_SETUP+= GIT_LOCATION=${GIT_LOCATION}
ENV_SETUP+= BUILD_TIMESTAMP=${BUILD_TIMESTAMP}
ENV_SETUP+= SEQUENCE=${TRAIN}-${BUILD_TIMESTAMP}
ENV_SETUP+= TRAIN=${TRAIN}
ENV_SETUP+= UPDATE_USER=sef	# For now, just use sef's account
ENV_SETUP+= FREENAS_KEYFILE=${FREENAS_KEYFILE}
.if exists(ChangeLog)
ENV_SETUP+= CHANGELOG=ChangeLog
.endif

.if defined(NANO_ARCH)
 ENV_SETUP+= NANO_ARCH=${NANO_ARCH}
.endif

all:	build

builder-verify:
	${ENV_SETUP} /bin/sh build/check_build_host.sh
.if !make(checkout) && !make(update) && !make(clean) && !make(distclean) && !make(git-internal) && !make(git-external)
	${ENV_SETUP} /bin/sh build/check_sandbox.sh
.endif

build: git-verify
	@[ `id -u` -eq 0 ] || ( echo "Sorry, you must be running as root to build this."; exit 1 )
	@${ENV_SETUP} ${MAKE} portsjail
	@${ENV_SETUP} ${MAKE} ports
	${ENV_SETUP} /bin/sh build/do_build.sh

checkout: git-verify
	${ENV_SETUP} /bin/sh build/do_checkout.sh

update: git-verify
	git pull
	${ENV_SETUP} /bin/sh build/do_checkout.sh

clean:
	${ENV_SETUP} build/build_cleanup.py
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
	${ENV_SETUP} ${MAKE} clean-package p=freenas-ui

distclean: clean
	rm -fr FreeBSD nas_source

save-build-env:
	${ENV_SETUP} /bin/sh build/save_build.sh

changelog:
	@if [ -f ChangeLog ]; then \
		echo ChangeLog already exists.; exit 1; \
	fi
	@if [ -f /root/redmine-api-key ]; then \
		if [ "${TRAIN}" == "FreeNAS-9.3-STABLE" ]; then \
			python build/create_redmine_changelog.py -k `cat /root/redmine-api-key` -p "freenas" > ChangeLog; \
		elif [ "${TRAIN}" == "TrueNAS-9.3-STABLE" ]; then \
			python build/create_redmine_changelog.py -k `cat /root/redmine-api-key` -p "truenas" > ChangeLog; \
		else \
			echo "I don't create ChangeLogs for ${TRAIN}"; \
		fi \
	fi

freenas: release
release: git-verify
	@if [ "${NANO_LABEL}" = "TrueNAS" -a "${GIT_LOCATION}" != "INTERNAL" ]; then echo "You can only run this target from an internal repository."; exit 2; fi
	@echo "Doing executing target $@ on host: `hostname`"
	@echo "Build directory: `pwd`"
	${ENV_SETUP} script -a ${RELEASE_LOGFILE} ${MAKE} build
	${ENV_SETUP} script -a ${RELEASE_LOGFILE} build/create_release_distribution.sh
	${ENV_SETUP} script -a ${RELEASE_LOGFILE} build/create_upgrade_distribution.sh
.if defined(JENKINS_STAGEDIR)
	@cp ReleaseNotes UPGRADING "objs/${STAGEDIR}/"
	@if [ -f ChangeLog ]; then cp ChangeLog "objs/${STAGEDIR}/"; fi
	cp -r "objs/${STAGEDIR}" "${JENKINS_STAGEDIR}"
.endif

release-push: release
	@echo ${KEY_PASSWORD} | ${ENV_SETUP} /bin/sh build/post-to-upgrade.sh objs/LATEST/
	rm -rf "${IX_INTERNAL_PATH}/${STAGEDIR}"
	rm -rf "objs/${STAGEDIR}/FreeNAS-MANIFEST objs/${STAGEDIR}/Packages"
	cp ReleaseNotes UPGRADING objs/${STAGEDIR}/
	if [ -f ChangeLog ]; then cp ChangeLog objs/${STAGEDIR}/; fi
	cp -r "objs/${STAGEDIR}" "${IX_INTERNAL_PATH}/${STAGEDIR}"
	${ENV_SETUP} /bin/sh build/post-to-download.sh "${IX_INTERNAL_PATH}" "${NANO_LABEL}-${VERSION}" "${TRAIN}" "${BUILD_TIMESTAMP}"
	if [ "${TRAIN}" == "FreeNAS-9.3-STABLE" ]; then \
		echo "Tell Matt to push his web update button again" | mail -s "Update ${STAGEDIR} now on download.freenas.org" web@ixsystems.com; \
		if [ -f /root/redmine-api-key ]; then ./build/create_redmine_version.py -k `cat /root/redmine-api-key` -v "${VERSION}-${BUILD_TIMESTAMP}" -d "9.3 Software Update released on ${PRINTABLE_TIMESTAMP} GMT"; fi; \
		mv "${IX_INTERNAL_PATH}/${STAGEDIR}" "${IX_STABLE_DIR}"/`echo ${STAGEDIR} | awk -F- '{print $$4}'`; \
		(cd "${IX_STABLE_DIR}"; rm -f latest; ln -s `echo ${STAGEDIR} | awk -F- '{print $$4}'` latest); \
		${ENV_SETUP} ${MAKE} save-build-env ; \
	fi

update-push:	release
	@echo ${KEY_PASSWORD} | ${ENV_SETUP} /bin/sh build/post-to-upgrade.sh objs/LATEST/

update-undo:
	${ENV_SETUP} ssh ${UPDATE_USER}@update.freenas.org freenas-release --archive /tank/www/${NANO_LABEL} --project ${NANO_LABEL} -D ~${UPDATE_USER}/FreeNAS-updates.db rollback ${TRAIN}

archive:	release
.if !defined(ARCHIVE)
	@echo "ARCHIVE location must be defined" 1>&2
	false
.endif
.if !defined(RELEASEDB)
	@echo "RELEASEDB must be defined" 1>&2
	false
.endif
	/usr/local/bin/freenas-release -P ${NANO_LABEL} \
		-D ${RELEASEDB} --archive ${ARCHIVE} \
		-K ${FREENAS_KEYFILE} \
		add objs/LATEST

rebuild:
	@${ENV_SETUP} ${MAKE} checkout
	@${ENV_SETUP} ${MAKE} all
	@${ENV_SETUP) /bin/sh build/create_release_distribution.sh

cdrom:
	${ENV_SETUP} /bin/sh -x build/create_iso.sh

# intentionally split up to prevent abuse/spam
BUILD_BUG_DOMAIN?=ixsystems.com
BUILD_BUG_USER?=build-bugs
BUILD_BUG_EMAIL?=${BUILD_BUG_USER}@${BUILD_BUG_DOMAIN}

build-bug-report:
	mail -s "build fail for $${SUDO_USER:-$$USER}" ${BUILD_BUG_EMAIL} < \
		${RELEASE_LOGFILE}

git-verify: builder-verify
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
	${ENV_SETUP} /bin/sh build/apply_tag.sh

ports:
	@[ `id -u` -eq 0 ] || (echo "Sorry, you must be running as root to build this."; exit 1)
	${ENV_SETUP} /bin/sh build/ports/create-poudriere-conf.sh
	${ENV_SETUP} /bin/sh build/ports/create-poudriere-make.conf.sh
	${ENV_SETUP} /bin/sh build/ports/prepare-jail.sh
	${ENV_SETUP} /bin/sh build/ports/fetch-ports-srcs.sh
	${ENV_SETUP} /bin/sh build/ports/create-ports-list.sh
	${ENV_SETUP} /bin/sh build/ports/build-ports.sh

portsjail:
	${ENV_SETUP} /bin/sh build/build_jail.sh
