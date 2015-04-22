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

BUILD_TIMESTAMP != date '+%Y%m%d'
BUILD_STARTED != date '+%s'
BUILD_ROOT ?= ${.CURDIR}
BUILD_CONFIG := ${BUILD_ROOT}/build/config
BUILD_TOOLS := ${BUILD_ROOT}/build/tools
PYTHONPATH := ${BUILD_ROOT}/build/lib
OBJDIR ?= ${BUILD_ROOT}/objs/amd64
MK := ${MAKE} -f ${BUILD_ROOT}/Makefile.inc1

GIT_REPO_SETTING=${BUILD_ROOT}/.git-repo-setting
.if exists(${GIT_REPO_SETTING})
GIT_LOCATION!=cat ${GIT_REPO_SETTING}
.endif

.export MK
.export GIT_LOCATION
.export BUILD_TIMESTAMP
.export BUILD_ROOT
.export BUILD_CONFIG
.export BUILD_TOOLS
.export PYTHONPATH
.export OBJDIR
.export BUILD_STARTED
.export GIT_REPO_SETTING

git-verify:
	@if [ ! -f ${GIT_REPO_SETTING} ]; then \
		echo "No git repo choice is set.  Please use \"make git-external\" to build as an"; \
		echo "external developer or \"make git-internal\" to build as an ${COMPANY}"; \
		echo "internal developer.  You only need to do this once."; \
		exit 1; \
	fi
	@echo "NOTICE: You are building from the ${GIT_LOCATION} git repo."

.BEGIN:
.if !make(remote) && !make(sync)
	@${BUILD_TOOLS}/buildenv.py ${BUILD_TOOLS}/check-host.py
.if !make(checkout) && !make(update) && !make(clean) && !make(distclean) && !make(git-internal) && !make(git-external)
	@${BUILD_TOOLS}/buildenv.py ${BUILD_TOOLS}/check-sandbox.py
.endif
.endif

buildenv:
	@${BUILD_TOOLS}/buildenv.py sh

.DEFAULT: git-verify
	@mkdir -p ${OBJDIR}
	@${BUILD_TOOLS}/buildenv.py ${MK} ${.TARGETS}
