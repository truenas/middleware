#!/bin/sh
#+
# Copyright 2011 iXsystems, Inc.
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


flame_opt() { echo E; }
flame_help() { echo "flame graphs for user and kernel profiling"; }
flame_directory() { echo "flame"; }
flame_func()
{
	local loaded=false
	local dtscript="$(realpath ${FREENAS_DEBUG_MODULEDIR}/flame/flame_kern_stacks.dtrace)"
	local dtustackscript="$(realpath ${FREENAS_DEBUG_MODULEDIR}/flame/flame_ustack.dtrace)"
	local collapsescript="$(realpath ${FREENAS_DEBUG_MODULEDIR}/flame/dtstackcollapse_flame.pl)"
	local flamescript="$(realpath ${FREENAS_DEBUG_MODULEDIR}/flame/flamegraph.pl)"

	section_header "flame graph generator"
	rm -f /tmp/collapsar /tmp/ucollapsar /tmp/stacks /tmp/ustacks
	(time dtrace -qs ${dtscript}  > /tmp/stacks ; echo stack done ) & 
	local kstackpid=$!
	(time dtrace -qs ${dtustackscript}  > /tmp/ustacks; echo ustack done )&
	local ustackpid=$!
	echo awaiting $kstackpid $ustackpid
	wait $kstackpid $ustackpid 
	
	echo "generating ${FREENAS_DEBUG_DIRECTORY}/${directory}/flame.svg"
	tail -1600 /tmp/stacks | ${collapsescript}  > /tmp/collapsar &&   \
		${flamescript} < /tmp/collapsar > ${FREENAS_DEBUG_DIRECTORY}/${directory}/flame.svg &
	local prockstackpid=$!
	echo "generating  ${FREENAS_DEBUG_DIRECTORY}/${directory}/userlandflame.svg"
	tail -1600 /tmp/ustacks | ${collapsescript}  > /tmp/ucollapsar && \ 
		${flamescript} < /tmp/ucollapsar > ${FREENAS_DEBUG_DIRECTORY}/${directory}/userlandflame.svg &
	local procustackpid=$!
	echo awaitng $prockstackpid $procustackpid
	wait $prockstackpid $procustackpid
	section_footer

}
