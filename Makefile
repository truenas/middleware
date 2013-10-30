
NANO_LABEL?=FreeNAS
VERSION?=9.2.0-ALPHA

RELEASE_LOGFILE=release.build.log
GIT_REPO_SETTING=.git-repo-setting
.if exists(${GIT_REPO_SETTING})
GIT_LOCATION!=cat ${GIT_REPO_SETTING}
.endif
ENV_SETUP=env NANO_LABEL=${NANO_LABEL} VERSION=${VERSION} GIT_LOCATION=${GIT_LOCATION}

all: git-verify
	@[ `id -u` -eq 0 ] || (echo "Sorry, you must be running as root to build this."; exit 1)
	${ENV_SETUP} build/do_build.sh

checkout: git-verify
	${ENV_SETUP} build/do_build.sh -c

clean:
	${ENV_SETUP} build/build_cleanup.py
	rm -rf FreeBSD os-base release_stage ${NANO_LABEL}-${VERSION}-release.tar release.build.log

save-build-env:
	${ENV_SETUP} build/save_build.sh

release:
	${ENV_SETUP} script -a ${RELEASE_LOGFILE} ${MAKE} do-release

do-release: git-verify
	@echo "Doing executing target $@ on host: `hostname`"
	@echo "Build directory: `pwd`"
	${ENV_SETUP} build/build_release.sh

cdrom:
	${ENV_SETUP} sh -x build/create_iso.sh

force: git-verify
	${ENV_SETUP} build/do_build.sh -fu

# Build truenas using all sources 
truenas-all-direct:
	${ENV_SETUP} TESTING_TRUENAS=1 NAS_PORTS_DIRECT=1 $(MAKE) all

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
		echo "external developer or \"make git-internal\" to build as an iXsystems"; \
		echo "internal developer.  You only need to do this once."; \
		exit 1; \
	fi
	@echo "NOTICE: You are building from the `cat ${GIT_REPO_SETTING}` git repo."

git-internal:
	@echo "INTERNAL" > ${GIT_REPO_SETTING}
	@echo "You are set up for internal (iXsystems) development.  You can use"
	@echo "the standard make targets (e.g. build or release) now."

git-external:
	@echo "EXTERNAL" > ${GIT_REPO_SETTING}
	@echo "You are set up for external (github) development.  You can use"
	@echo "the standard make targets (e.g. build or release) now."
