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

in=${1-schema.init}
db=${2-/tmp/database-v1.db}

sed -e 's/#.*$//' < $in | \
awk '
BEGIN {
	# tick is here because it is hard to quote right...  We have to do
	# this dance because a simple \ escape does not work and we are inside
	# a shell tick environment now...
	tick="'"'"'";
	num=0;
}

# Function to dump out the tables that we have parsed so far.
function dump_tables(tbl, cols, vals, num) {
	if (num == 0) {
		return 0;
	}
	_c="";
	_v="";
	_sep=",";
	for (i = 0; i < num; i++) {
		if (i == num - 1) {
			_sep="";
		}
		_c=_c cols[i] _sep;
		_v=_v tick vals[i] tick _sep;
	}
	print "INSERT INTO " tbl "(" _c ") VALUES(" _v ");";
}
/TABLE/ {
	tbl = $2;
	num = 0;
}
/=/ {
	sub("^[ \t]*", "");	# Strip leading white space
	a = index($0, "=");
	col = substr($0, 1, a-1);
	val = substr($0, a + 1, length($0));
	sub("^\"", "", val);
	sub("\"$", "", val);
	vals[num] = val;
	cols[num] = col;
	num++;
}
/^}/ {
	dump_tables(tbl, cols, vals, num);
}
' | sqlite3 -batch -echo -bail $db
