#!/bin/sh
#+
# Copyright 2010 iXsystems
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
# schema.init looks like:
#
# TABLE table {
#	v1=val
#	v2=blah
# }
# TABLE table2 {
#	vc1=val
#	re2=blah
# }
#
# etc, and inserts one row into the table for each table statement.
# this implies you can insert multiple rows into a table if you list the
# same table many times...
#

# For debugging, you can s/^#D#//g on this file to have it create the database
# from scratch (assuming schema and the python code is in sync).

in=${1-schema.init}
db=${2-/tmp/database-v1.db}

#D#rm -f $db
sed -e 's/#.*$//' < $in | \
awk '
BEGIN {
	# tick is here because it is hard to quote right...  We have to do
	# this dance because a simple \ escape does not work as we are inside
	# a shell tick environment now...
	tick="'"'"'";
#D#	print ".read schema";
}

/TABLE/ {
	tbl = $2;
	num = 0;
}
/=/ {
	sub("^[ \t]*", "");	# Strip leading white space
	split($0, a, "=");
	cols[num] = a[1];
#	gsub("\\\\n", tick " + chr(10) + " tick, a[2]);
	vals[num] = tick a[2] tick;
	num++;
}
/^}/ {
	if (num != 0) {
		_c=cols[0];
		_v=vals[0];
		for (i = 1; i < num; i++) {
			_c=_c "," cols[i];
			_v=_v "," vals[i];
		}
		print "INSERT INTO " tbl "(" _c ") VALUES(" _v ");";
	}
}
' | sqlite3 -batch -echo -bail $db
