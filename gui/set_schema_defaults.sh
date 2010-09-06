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
# $FreeBSD$
#####################################################################

SCHEMA=$1
DEFAULTS=$2
${FREENAS_DATABASE_PATH="/data/freenas-v1.db"}

usage()
{
	echo "Usage: $0 <schema> <file>"
}

get_table_schema()
{
	local _database
	local _table
	local _schema

	_database=$1
	_table=$2

	_schema=`echo ".schema $_table" | sqlite3 "$_database" 2>/dev/null`
	VAL="$_schema"

	export VAL
}

get_table_columns()
{
	local _database
	local _table

	_database=$1
	_table=$2

	_columns=`echo ".schema $_table" \
		| sqlite3 "$_database" \
		| grep -E '^ +"' \
		| grep -iv 'PRIMARY KEY' \
		| grep -i "NOT NULL" \
		| awk '{ print $1 }' \
		| sed 's|"||g' \
		| sort \
		| xargs`
	VAL="$_columns"

	export VAL
}

get_primary_key()
{
	local _database
	local _table
	local _pkey

	_database=$1
	_table=$2

	_pkey=`echo ".schema $_table" \
		| sqlite3 "$_database" \
		| grep "PRIMARY KEY" \
		| xargs \
		| awk '{ print $1 }' 2>/dev/null`
	VAL="$_pkey"

	export VAL
}

get_table_defaults()
{
	local _file
	local _table
	local _defaults

	_file=$1
	_table=$2

	_defaults=`grep -w "$_table" "$_file" 2>/dev/null`
	VAL="$_defaults"

	export VAL
}

check_columns()
{
	local _table
	local _columns
	local _defaults
	local _notset
	local _res

	_table=$1
	_columns=$2
	_defaults=$3

	_res=0
	_notset=""
	for _col in $_columns
	do
		local _set

		_set=0
		for _d in $_defaults
		do
			_dcol=`echo $_d | cut -f2 -d. | cut -f1 -d=`
			if [ "$_col" = "$_dcol" ]
			then
				_set=1
				break
			fi
		done

		if [ "$_set" = "0" ]
		then
			_notset="${_notset}${_col} "
		else
			_set=0
		fi

	done

	VAL="$_notset"
	export VAL

	if [ -n "$_notset" ]
	then
		_res=1
	fi

	return $_res
}

getval()
{
	local _str
	local _tmp
	local _val

	_str=$1
	_tmp=`echo "$_str" | cut -f2 -d=`
	_val=`echo "$_tmp" | sed -E 's|^"(.*)"$|\1|'`

	VAL="$_val"
	export VAL
}

get_column_value()
{
	local _nlines
	local _column
	local _file
	local _ret
	local _i
	local _n

	_column=$1
	_file=$2

	if [ ! -f "${_file}" ]
	then
		return 1
	fi

	_ret=""
	_nlines=`cat "${_file}" | wc -l`

	_i=0; _n=1;
	while [ "${_i}" -lt "${_nlines}" ]
	do
		local _line
		local _col
		local _val

		_line=`head -n "${_n}" "${_tmpfile}" | tail -1`
		_col=`echo "$_line" | cut -f2 -d. | cut -f1 -d=`
		_val=`echo "$_line" | cut -f2 -d=`

		if [ "$_column" = "$_col" ]
		then
			getval "$_val"
			_ret="$VAL"
			break
		fi

		_i=`expr ${_i} + 1`
		_n=`expr ${_n} + 1`
	done

	VAL="$_ret"
	export VAL

	return 0
}

generate_sql()
{
	local _table
	local _columns
	local _defaults
	local _tmpfile
	local _nlines
	local _colstr
	local _valstr
	local _file
	local _sql
	local _i
	local _n

	_table=$1
	_columns=$2
	_defaults=$3
	_file=$4

	if [ -z "$_columns" ]
	then
		return 1
	fi

	_colstr=""
	_valstr=""
	_tmpfile="${TMPDIR}/${_table}"

	echo "${_defaults}" > "${_tmpfile}"
	_nlines=`cat "${_tmpfile}" | wc -l`

	_i=0; _n=1;
	while [ "${_i}" -lt "${_nlines}" ]
	do
		local _line

		_line=`head -n "${_n}" "${_tmpfile}" | tail -1`
		_col=`echo "$_line" | cut -f2 -d. | cut -f1 -d=`
		_colstr="${_colstr}${_col},"

		get_column_value "$_col" "$_tmpfile"
		_valstr="${_valstr}'${VAL}',"

		_i=`expr ${_i} + 1`
		_n=`expr ${_n} + 1`
	done

	_colstr=`echo "$_colstr" | sed -E 's|,$||'`
	_valstr=`echo "$_valstr" | sed -E 's|,$||'`

	_sql="INSERT INTO $_table($_colstr) VALUES($_valstr)"
	VAL="$_sql"

	echo "$VAL" >> "$_file"
	export VAL

	rm "${_tmpfile}"
	return 0
}

import_sql()
{
	local _db
	local _file
	local _line

	_db=$1
	_file=$2

	if [ -z "$_db" ] || [ -z "$_sqlfile" ]
	then
		return 1
	fi

	exec 3<&0
	exec 0<"$_file"
	while read -r _line
	do
		sqlite3 -echo -bail "$_db" "$_line" 
		if [ "$?" -ne "0" ]
		then
			return 1
		fi
	done
	exec 0<&3

	rm -f "$_linefile"
	return 0
}

main()
{
	local _db
	local _schema
	local _defaults
	local _errfile
	local _sqlfile
	local _file
	local _tables
	local _res

	_db=$1
	_schema=$2
	_defaults=$3

	_res=0
	_file="${TMPDIR}/sortout"
	_errfile="${TMPDIR}/errout"
	_sqlfile="${TMPDIR}/sqlout"

	grep -Ev '^( *|#.*| *#.*)$' < "$_defaults" \
		| sed -E 's|^ +||' \
		| sed -E 's| *(=) *|\1|' \
		| sed -E 's|#.+$||g' \
		| sort -u > "$_file" 2>/dev/null

	_tables=`grep -Ev '^ *$' < "$_file" \
		| sed -E 's|^ +||' \
		| sed -E 's| *(=) *|\1|' \
		| cut -f1 -d. \
		| sort -u`

	for _t in $_tables
	do
		local _table_defaults
		local _columns
		local _notset

		get_table_defaults "$_file" "$_t"
		_table_defaults="$VAL"

		get_table_columns "$_db" "$_t"
		_columns="$VAL"

		generate_sql "$_t" "$_columns" \
			"$_table_defaults" "$_sqlfile"
	done

	import_sql "$_db" "$_sqlfile"
	_res=$?

	rm -f "$_file" "$_sqlfile" "$_errfile"
	return $_res
}


if [ -z "$SCHEMA" ] || [ -z "$DEFAULTS" ]
then
	usage;
	exit 1
else
	main "$FREENAS_DATABASE_PATH" "$SCHEMA" "$DEFAULTS"
	exit $?
fi
