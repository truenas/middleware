#!/usr/bin/env python
#- 
# Copyright (c) 2010 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

""" Helper for FreeNAS to execute command line tools

This helper class abstracts operating system operations like starting,
stopping, restarting services out from the normal Django stuff and makes
future extensions/changes to the command system easier.  When used as a
command line utility, this helper class can also be used to do these
actions.
"""

class notifier:
	from os import system as __system
	def _do_nada(self):
		pass
	def _simplecmd(self, action, what):
		try:
			f = getattr(self, '_' + action + '_' + what)
		except AttributeError:
			""" Provide generic start/stop/restart verbs for rc.d scripts """
			if action in ("start", "stop", "restart"):
				self.__system("/usr/sbin/service " + what + " " + action)
				f = self._do_nada
			else:
				raise "Internal error: Unknown command"
		try:
			f()
		except:
			raise "Execution failed"
	def start(self, what):
		""" Start the service specified by "what".
		
		The helper will use method self._start_[what]() to start the service.
		If the method does not exist, it would fallback using service(8)."""
		self._simplecmd("start", what)
	def stop(self, what):
		""" Stop the service specified by "what".
		
		The helper will use method self._stop_[what]() to stop the service.
		If the method does not exist, it would fallback using service(8)."""
		self._simplecmd("stop", what)
	def restart(self, what):
		""" Restart the service specified by "what".
		
		The helper will use method self._restart_[what]() to restart the service.
		If the method does not exist, it would fallback using service(8)."""
		self._simplecmd("restart", what)
	def reload(self, what):
		""" Reload the service specified by "what".
		
		The helper will use method self._reload_[what]() to reload the service.
		If the method does not exist, the helper will try self.restart the service instead."""
		try:
			self._simplecmd("reload", what)
		except:
			self.restart(what)
	def change(self, what):
		""" Notify the service specified by "what" about a change.
		
		The helper will use method self.reload(what) to reload the service.
		If the method does not exist, the helper will try self.start the service instead."""
		try:
			self.reload(what)
		except:
			self.start(what)
	def _start_network(self):
		self.__system("/etc/netstart")
	def _reload_named(self):
		self.__system("/usr/sbin/service named reload")

def usage():
	print ("Usage: %s action command" % argv[0])
	print "    Action is one of:"
	print "        start: start a command"
	print "         stop: stop a command"
	print "      restart: restart a command"
	print "       reload: reload a command (try reload, if unsuccessful do restart"
	print "       change: notify change for a command (try self.reload, if unsuccessful do start)"
	exit

# When running as standard-alone script
if __name__ == '__main__':
	from sys import argv
	if len(argv) != 3:
		usage()
	else:
		n = notifier()
		try:
			f = getattr(n, argv[1])
		except:
			print ("Unknown action: %s" % argv[1])
			usage()
		f(argv[2])
