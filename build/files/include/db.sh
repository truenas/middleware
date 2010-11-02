#!/bin/sh

: ${FREENAS_DATABASE:="/data/freenas-v1.db"}

schema_network_globalconfiguration()
{
	local _columns
	local _schema

	_columns="\
		id \
		gc_hostname \
		gc_domain \
		gc_ipv4gateway \
		gc_ipv6gateway \
		gc_nameserver1 \
		gc_nameserver2 \
		gc_nameserver3 \
	"

	_schema=`echo "${_columns}" | xargs`
	VAL="${_schema}"
	export VAL
}

schema_network_interfaces()
{
	local _columns
	local _schema

	_columns="\
		id \
		int_interface \
		int_name \
		int_dhcp \
		int_ipv4address \
		int_ipv6auto \
		int_ipv6address \
		int_options \
	"

	_schema=`echo "${_columns}" | xargs`
	VAL="${_schema}"
	export VAL
}

get_schema()
{
	local _table
	local _schema
	local _func

	_table="${1}"
	if [ -z "${_table}" ]
	then
		return 1
	fi

	_func=$(eval "echo schema_${_table}")
	eval "${_func}"
	_schema="${VAL}"

	return 0
}

build_columns_string()
{
	local _table
	local _schema
	local _str
	local _ifs

	_table="${1}"
	if [ -z "${_table}" ]
	then
		return 1
	fi

	get_schema "${_table}"
	_schema="${VAL}"

	_ifs="${IFS}"
	IFS=" "
	for _col in ${_schema}
	do
		_str="${_str},${_col}"
	done
	IFS="${_ifs}"

	_str=`echo "${_str}" | sed -e 's|^,||' -e 's|,$||'`
	VAL="${_str}"
	export VAL

	return 0
}

db_execute()
{
	local _sql
	local _sqlfile
	local _outfile
	local _res

	_sql="${1}"
	if [ -z "${_sql}" ]
	then
		return 1
	fi

	_sqlfile=/tmp/sql.txt
	_outfile=/tmp/out.txt

	_res=0
	echo "${_sql}" > "${_sqlfile}"
	sqlite3 -bail "${FREENAS_DATABASE}" < "${_sqlfile}" > "${_outfile}"
	_res=$?

	VAL=`cat "${_outfile}"`
	rm -f "${_sqlfile}" "${_outfile}"

	export VAL
	return ${_res}
}

db_insert_network_interface()
{
	local _table
	local _schema
	local _cols
	local _vals
	local _sql
	local _res
	local _ifs

	_ifs="${IFS}"
	IFS=" "

	_table="network_interfaces"
	get_schema "${_table}"
	_schema="${VAL}"

	while [ "${#}" -gt "0" ]
	do
		local _var=`echo "${1}" | cut -f1 -d=`
		local _val=`echo "${1}" | cut -f2 -d=`

		for _col in ${_schema}
		do
			if [ "${_col}" = "${_var}" ]
			then
				_cols="${_cols},${_col}"
				_vals="${_vals},'${_val}'"
				break
			fi
		done

		shift
	done

	_cols=`echo "${_cols}" | sed -e 's|^,||' -e 's|,$||'`
	_vals=`echo "${_vals}" | sed -e 's|^,||' -e 's|,$||'`

	_sql="insert into ${_table}(${_cols}) values(${_vals});"
	db_execute "${_sql}"
	_res=$?
	export VAL

	IFS="${_ifs}"
	return ${_res}
}

db_update_network_interface()
{
	local _iface
	local _column
	local _value
	local _table
	local _res
	local _sql
	local _ifs

	_iface="${1}"
	_column="${2}"
	_value="${3}"

	if [ -z "${_iface}" -o \
		-z "${_column}" -o \
		-z "${_value}" ]
	then
		return 1
	fi

	_ifs="${IFS}"
	IFS=" "

	_table="network_interfaces"
	_sql="update ${_table} set ${_column}='${_value}' \
		where int_interface='${_iface}';"
	
	db_execute "${_sql}"
	_res=$?
	export VAL

	IFS="${_ifs}"
	return ${_res}
}

db_update_network_globalconfiguration()
{
	local _table
	local _column
	local _ifs

	_column="${1}"
	_value="${2}"

	if [ -z "${_column}" -o \
		-z "${_value}" ]
	then
		return 1
	fi

	_ifs="${IFS}"
	IFS=" "

	_table="network_globalconfiguration"
	_sql="update ${_table} set ${_column}='${_value}';"

	db_execute "${_sql}"
	_res=$?
	export VAL

	IFS="${_ifs}"
	return ${_res}
}

db_get_network_interfaces()
{
	local _table
	local _str
	local _sql
	local _res
	local _columns
	local _ifs

	_ifs="${IFS}"
	IFS=" "

	_table="network_interfaces"
	build_columns_string "${_table}"
	_columns="${VAL}"

	_sql="select ${_columns} from ${_table};"

	db_execute "${_sql}"
	_res=$?
	export VAL

	IFS="${_ifs}"
	return ${_res}
}

db_get_network_interface()
{
	local _table
	local _str
	local _sql
	local _columns
	local _iface
	local _res
	local _ifs

	_iface="${1}"
	if [ -z "${_iface}" ]
	then
		return 1
	fi

	_ifs="${IFS}"
	IFS=" "

	_table="network_interfaces"
	build_columns_string "${_table}"
	_columns="${VAL}"

	_sql="select ${_columns} from ${_table} where int_interface = '${_iface}';"

	db_execute "${_sql}"
	_res=$?
	export VAL

	IFS="${_ifs}"
	return 0
}

db_get_network_globalconfiguration()
{
	local _table
	local _str
	local _sql
	local _res
	local _columns
	local _ifs

	_ifs="${IFS}"
	IFS=" "

	_table="network_globalconfiguration"
	build_columns_string "${_table}"
	_columns="${VAL}"

	_sql="select ${_columns} from ${_table};"

	db_execute "${_sql}"
	_res=$?
	export VAL

	IFS="${_ifs}"
	return ${_res}
}
