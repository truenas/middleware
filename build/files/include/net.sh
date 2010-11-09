#!/bin/sh

get_interface_list()
{
	local _ifaces

	_ifaces=`netstat -inW -f link | \
		tail +2 | \
		grep -Ev '^(ppp|sl|gif|faith|lo|vlan|tun|plip)' | \
		cut -f1 -d'*' | \
		awk '{ print $1 }'`

	VAL=""
	for i in ${_ifaces}
	do
		local _mac
		local _status
		local _up

		ifconfig "${i}" >/dev/null 2>&1
		if [ "$?" != "0" ]
		then
			continue
		fi

		_up="false"
		_mac=`ifconfig "${i}"|grep -E 'ether '|awk '{ print $2 }'`
		_status=`ifconfig "${i}"|grep status|awk '{ print $2 }'`
		if [ "${_status}" = "active" -o "${_status}" = "associated" ]
		then
			_up="true"
		fi

		if [ -n "${VAL}" ]
		then
			VAL="${VAL}|${i} ${_mac} ${_up}"
		else
			VAL="${i} ${_mac} ${_up}"
		fi

	done

	export VAL
}

autodetect_interface()
{
	local _ifname
	local _iflist_pre
	local _iflist_post
	local _tmpfile
	local _msg

	_ifname="${1}"

	get_interface_list;
	_iflist_pre="${VAL}"

	_tmpfile="/tmp/msg"
	cat << EOD > "${_tmpfile}"
Connect the ${_ifname} interface now and make
sure that the link is up.
Press OK to continue.
EOD
	_msg=`cat "${_tmpfile}"`
	rm -f "${_tmpfile}"

	dialog --clear --msgbox "${_msg}" 7 52

	get_interface_list;
	_iflist_post="${VAL}"

	for i in ${_iflist_pre}
	do
		local _iface_pre
		local _up_pre

		_iface_pre=`echo "${i}"|awk '{ print $1 }'`
		_up_pre=`echo "${i}"|awk '{ print $3 }'`

		for j in ${_iflist_post}
		do
			local _iface_post
			local _up_post

			_iface_post=`echo $j|awk '{ print $1 }'`
			_up_post=`echo $j|awk '{ print $3 }'`

			if [ "${_iface_pre}" = "${_iface_post}" \
				-a "${_up_post}" = "up" \
				-a "${_up_pre}" != "${_up_post}" ]
			then
				dialog --clear \
					--msgbox "Detected link-up on interface ${_iface_pre}" 5 44
				VAL="${_iface_pre}"
				export VAL

				return 0
			fi
		done
	done

	VAL=""
	export VAL

	dialog --clear --msgbox "No link-up detected." 5 24
	return 1
}

configure_ipv4_dhcp()
{
	local _iface="${1}"
	local _found

	db_get_network_interface "${_iface}"
	_found="${VAL}"

	if [ -n "${_found}" ]
	then
		db_update_network_interface \
			"${_iface}" "int_dhcp" "1"

	else
		db_insert_network_interface \
			"int_interface=${_iface}" \
			"int_dhcp=1" \
			"int_name=" \
			"int_ipv4address=" \
			"int_ipv6address=" \
			"int_ipv6auto=" \
			"int_options="
	fi
}

configure_ipv6_auto()
{
	local _iface="${1}"
	local _found

	db_get_network_interface "${_iface}"
	_found="${VAL}"

	if [ -n "${_found}" ]
	then
		db_update_network_interface \
			"${_iface}" "int_ipv6auto" "1"

	else
		db_insert_network_interface \
			"int_interface=${_iface}" \
			"int_dhcp=" \
			"int_name=" \
			"int_ipv4address=" \
			"int_ipv6address=" \
			"int_ipv6auto=1" \
			"int_options="
	fi
}

get_ipv4_cidr_netmask()
{
	local _mask="${1}"
	[ -z "${_mask}" ] && return 1

	local _cidr=`echo "${_mask}" | awk '{
		mask = $1 + 0;
		count = 0;

		if (mask == 1) {
			count++;

		} else {
			while (mask >= 1) {
				mask = mask / 2;
				if (mask % 1)
					count++;
			}
		}

		printf("%d", count);
	}'`

	VAL="${_cidr}"
	export VAL

	return 0
}

get_ipv4_dotted_netmask()
{
	local _mask="${1}"
	[ -z "${_mask}" ] && return 1

	local _dotted=`echo "${_mask}" | awk '{
		mask = $1;
		len = length(mask);

		if (mask ~ /0[xX]/) {
			len -= 2;
			mask = substr(mask, 3, len);
		}

		if (len > 8)
			len = 8;

		if (len < 8) {
			slen = len;
			for (i = 0;i < 8 - slen;i++) {
				mask = mask "0";
				len++;
			}
		}

		i = pos = 0;
		parts[0] = null;
		while (pos <= len) {
			size = 2;
			if (len - pos < 2)
				size = len - pos;
			
			parts[i] = substr(mask, pos + 1, size);
			pos += 2;
			i++;
		}

		str = null;
		for (i = 0;i < 4;i++) {
			tmp = 0;

			if (parts[i])
				tmp = ("0x" parts[i]) + 0;

			str = str sprintf("%03d", tmp);
			if (i < 3)
				str = str ".";
		}

		printf("%s", str);
	}'`

	VAL="${_dotted}"
	export VAL

	return 0
}

netmask_to_cidr()
{
	local _mask="${1}"
	[ -z "${_mask}" ] && return 1

	unset VAL
	local _res=1

	if echo "${_mask}" | grep '\.' >/dev/null
	then
		_mask=`echo "${_mask}" | awk '{
			mask = $1;
			parts[0] = null;

			str = "0x";
			len = split(mask, parts, ".");
			for (i = 1;i <= len;i++) {
				str = str sprintf("%02x", parts[i]);
			}

			printf("%s", str);
		}'`

		get_ipv4_cidr_netmask "${_mask}"
		_res=0
	else	
		VAL="${_mask}"
	fi

	export VAL
	return ${_res}
}

get_dnsserver()
{
	local _config
	local _dnsserver
	local _ipv

	_ipv="${1}"

	unset VAL
	db_get_network_globalconfiguration
	_config="${VAL}"
	[ -z "${_config}" ] && return 1

	unset VAL
	_dnsserver=`echo "${_config}"|cut -f6 -d'|'`
	[ -z "${_dnsserver}" ] && return 1

	VAL="${_dnsserver}"
	export VAL

	return 0

}

get_gateway()
{
	local _config
	local _gateway
	local _ipv

	_ipv="${1}"

	unset VAL
	db_get_network_globalconfiguration
	_config="${VAL}"
	[ -z "${_config}" ] && return 1

	case "${_ipv}" in
		ipv4|*) _gateway=`echo "${_config}"|cut -f4 -d'|'` ;;
		ipv6) _gateway=`echo "${_config}"|cut -f5 -d'|'` ;;
	esac

	[ -z "${_gateway}" ] && return 1
	VAL="${_gateway}"
	export VAL

	return 0
}

get_netmask()
{
	local _iface
	local _cidr
	local _ipv
	local _res
	local _mask

	_ipv="${1}"
	_iface="${2}"
	_cidr="${3}"

	[ -z "${_ipv}" ] && return 1
	[ -z "${_iface}" ] && return 1

	_res=0
	unset VAL
	case "${_ipv}" in 
		ipv4|*)
			_mask=`ifconfig "${_iface}"|grep 'inet '|awk '{ print $4 }'|head -1`
			[ -z "${_mask}" ] && return 1

			if [ -n "${_cidr}" ]
			then
				get_ipv4_cidr_netmask "${_mask}"
			else
				get_ipv4_dotted_netmask "${_mask}"
			fi
			_res=$?
			;;

		ipv6)
			_mask=`ifconfig "${_iface}"|grep 'inet6 '|awk '{ print $4 }'|head -1`
			[ -z "${_mask}" ] && return 1

			VAL="${_mask}"
			;;
	esac

	export VAL
	return ${_res}
}

get_ipaddress()
{
	local _ipv
	local _iface
	local _res
	local _ip

	_ipv="${1}"
	_iface="${2}"
	[ -z "${_iface}" ] && return 1

	_res=0
	unset VAL
	case "${_ipv}" in
		ipv4|*) _ip=`ifconfig "${_iface}"|grep 'inet '|awk '{ print $2 }'|head -1` ;;
		ipv6) _ip=`ifconfig "${_iface}"|grep 'inet6 '|awk '{ print $2 }'|head -1` ;;
	esac

	[ -z "${_ip}" ] && _res=1
	VAL="${_ip}"
	export VAL

	return ${_res}

}

is_ipv6hex()
{
	local _hex
	local _len
	local _res
	local _i

	_hex="${1}"
	_len="${#_hex}"

	[ "${_hex}" != "0" -a "${_len}" = "1" ] && return 1
	[ "${_len}" -gt "4" ] && return 1

	_i=1
	_res=0
	while [ "${_i}" -le "${_len}" ]
	do
		local _byte=`echo "${_hex}"|cut -b "${_i}"`
		echo "${_byte}"|awk '/^[0-9a-fA-F]/ { exit(1); }'
		if [ "$?" = "0" ]
		then
			_res=1
			break
		fi

		_i=`expr "${_i}" + 1`
	done

	return ${_res}
}

#
# This needs work :-)
#
is_ipv6addr()
{
	local _addr
	local _ifs
	local _res
	local _count

	_addr="${1}"
	[ -z "${_addr}" ]  && return 1

	_ifs="${IFS}"
	IFS=":"

	_res=0
	_count=0
	for _a in ${_addr}
	do
		if ! is_hex "${_a}"
		then
			_res=1
			break
		fi
	done
	IFS="${_ifs}"

	[ "${_count}" -lt "2" ] && return 1
	[ "${_count}" -gt "7" ] && return 1

	return ${_res}
}

is_ipv4addr()
{
	local _ifs
	local _valid
	local _parts
	local _ip

	_ip="${1}"
	_ifs="${IFS}"
	IFS="."

	_parts=0
	_valid=0
	for _oct in ${_ip}
	do
		_parts=`expr "${_parts}" + 1`
		_oct=`expr "${_oct}" + 0`
		if [ "${_oct}" -lt "0" -o "${_oct}" -gt "255" ]
		then
			_valid=1
			break
		fi
	done

	if [ "${_parts}" = "0" -o "${_parts}" -gt "4" ]
	then
		_valid=1
	fi

	IFS="${_ifs}"
	return ${_valid}
}

is_ipaddr()
{
	# For now ....
	return 0
}

is_ipv6mask()
{
	local _mask="${1}"

	local _res=1
	if [ "${_mask}" -ge "1" -a "${_mask}" -le "128" ]
	then
		_res=0
	fi

	return ${_res}
}

is_ipv4mask()
{
	local _mask="${1}"
	[ -z "${_mask}" ] && return 1

	local _res=1
	if echo "${_mask}"|egrep '\.' > /dev/null
	then
		local _parts=0
		local _ifs="${IFS}"
		IFS="."

		for _oct in ${_mask}
		do
			_parts=`expr "${_parts}" + 1`
			_oct=`expr "${_oct}" + 0`
			if [ "${_oct}" -ge "0" -a "${_oct}" -le "255" ]
			then
				_res=0
				break
			fi
		done

		[ "${_parts}" = "0" -o "${_parts}" -gt "4" ] && _res=1
		IFS="${_ifs}"

	else
		[ "${_mask}" -ge "1" -a "${_mask}" -le "32" ] && _res=0
	fi

	return ${_res}
}

is_mask()
{
	local _ipv
	local _mask
	local _res

	_ipv="${1}"
	_mask="${2}"

	[ -z "${_mask}" ] && return 1

	_res=1
	case "${_ipv}" in
		ipv4|*)
			is_ipv4mask "${_mask}"
			_res=$?
			;;

		ipv6)
			is_ipv6mask "${_mask}"
			_res=$?
			;;
	esac

	return ${_res}
}

prompt_netmask()
{
	local _iface
	local _mask
	local _loop
	local _tmpfile
	local _mask
	local _ipv4
	local _txt
	local _code

	_ipv="${1}"
	_iface="${2}"
	[ -z "${_iface}" ] && return 1

	_loop=1
	_tmpfile="/tmp/answer.txt"

	_mask="${3}"
	case "${_ipv4}" in
		ipv4|*)
			_txt="Enter new LAN subnet mask."
			_code="{
				netmask_to_cidr ${_mask}
				_mask=${VAL}
			}"
			;;
		ipv6)
			_txt="Enter prefix."
			_code="{ : }"
			;;
	esac

	while [ "${_loop}" = "1" ]
	do
		dialog --clear --inputbox "${_txt}" \
			8 35 "${_mask}" 2>"${_tmpfile}"
		[ "$?" = "0" ] || exit 1

		_mask=`cat "${_tmpfile}"`
		rm -f "${_tmpfile}"

		# Is valid netmask?
		if is_mask "${_ipv}" "${_mask}"
		then
			_loop=0
		fi

		case "${_ipv4}" in
			ipv4|*)
				netmask_to_cidr "${_mask}"
				_mask="${VAL}"
				;;
		esac
	done

	VAL="${_mask}"
	export VAL

	return 0

}

prompt_gateway()
{
	local _gatewayip
	local _loop
	local _tmpfile
	local _ipv
	local _txt

	_ipv="${1}"
	[ -z "${_ipv}" ] && return 1

	get_gateway "${_ipv}"
	_gatewayip="${VAL}"

	_loop=1
	_tmpfile="/tmp/answer.txt"

	case "${_ipv}" in
		ipv4|*) _txt="Enter IPv4 default gateway." ;;
		ipv6) _txt="Enter IPv6 default gateway." ;;
	esac

	while [ "${_loop}" = "1" ]
	do
		dialog --clear --inputbox "${_txt}" \
			8 35 "${_gatewayip}" 2>"${_tmpfile}"
		[ "$?" = "0" ] || exit 1

		_gatewayip=`cat "${_tmpfile}"`
		rm -f "${_tmpfile}"

		# Is valid IP?
		if is_ipaddr "${_gatewayip}"
		then
			_loop=0
		fi
	done

	VAL="${_gatewayip}"
	export VAL

	return 0
}

prompt_dnsserver()
{
	local _dnsserverip
	local _loop
	local _tmpfile
	local _ipv
	local _txt

	_ipv="${1}"
	[ -z "${_ipv}" ] && return 1

	get_dnsserver "${_ipv}"
	_dnsserverip="${VAL}"

	_loop=1
	_tmpfile="/tmp/answer.txt"
	case "${_ipv}" in
		ipv4|*) _txt="Enter DNS IPv4 address." ;;
		ipv6) _txt="Enter DNS IPv6 address." ;;
	esac

	while [ "${_loop}" = "1" ]
	do
		dialog --clear --inputbox "${_txt}" \
			8 35 "${_dnsserverip}" 2>"${_tmpfile}"
		[ "$?" = "0" ] || exit 1

		_dnsserverip=`cat "${_tmpfile}"`
		rm -f "${_tmpfile}"

		# Is valid IP?
		local _bad=0
		local _ifs="${IFS}"
		IFS=","

		for _d in ${_dnsserverip}
		do
			if ! is_ipaddr "${_d}"
			then
				_bad=`expr "${_bad}" + 1`
			fi
		done

		[ "${_bad}" = "0" ] && _loop=0
		IFS="${_ifs}"
	done

	VAL="${_dnsserverip}"
	export VAL

	return 0
}

prompt_ipaddress()
{
	local _ipv
	local _iface
	local _lanip
	local _loop
	local _tmpfile
	local _txt

	_loop=1
	_tmpfile="/tmp/answer.txt"
	_ipv="${1}"

	_iface="${2}"
	[ -z "${_iface}" ] && return 1

	_lanip="${3}"
	case "${_ipv}" in
		ipv4|*) _txt="Enter new LAN IPv4 address." ;;
		ipv6) _txt="Enter new LAN IPv6 address." ;;
	esac

	while [ "${_loop}" = "1" ]
	do
		dialog --clear --inputbox "${_txt}" \
			8 35 "${_lanip}" 2>"${_tmpfile}"
		[ "$?" = "0" ] || exit 1

	    _lanip=`cat "${_tmpfile}"`
		rm -f "${_tmpfile}"

		_loop=0

		# Is valid IP?
		if is_ipaddr "${_ipv}" "${_lanip}"
		then
			_loop=0
		fi

	done

	VAL="${_lanip}"
	export VAL

	return 0
}

configure_interface()
{
	local _ipv
	local _args
	local _iface
	local _txt
	local _func

	_ipv="${1}"
	_args="${2}"

	[ -z "${_ipv}" ] && return 1
	[ -z "${_args}" ] && return 1

	_iface=`echo "${_args}" | awk '{ print $1 }'`
	case "${_ipv}" in
		ipv4|*)
			_ipv="ipv4"
			_txt="Do you want to use IPv4 DHCP for interface (${_iface}?)"
			_func="configure_ipv4_dhcp"
			;;

		ipv6)
			_txt="Do you want to enable IPv6 autoconfiguration for interface (${_iface})?"
			_func="configure_ipv6_auto"
			;;
	esac

	dialog --clear --yesno "${_txt}" 5 75
	if [ "$?" = "0" ]
	then
		eval "${_func} ${_iface}"

	else
		local _found
		local _lanip
		local _loop
		local _mask
		local _gatewayip
		local _dnsserverip
		local _dhcp
		local _auto
		local _tmp
		local _f1
		local _f2
		local _c

		db_get_network_interface "${_iface}"
		_found="${VAL}"

		case "${_ipv}" in
			ipv4) _f1=4; _f2=5; _c="int_dhcp" ;;
			ipv6) _f1=6; _f2=7; _c="int_ipv6auto" ;;
		esac

		_tmp=`echo "${_found}"|cut -f"${_f1}" -d'|'`
		if [ "${_tmp}" = "1" ]
		then
			get_ipaddress "${_ipv}" "${_iface}"
			_lanip="${VAL}"

			if [ -z "${_lanip}" ]
			then
				_lanip=`echo "${_found}"|cut -f"${_f2}" -d'|'`
			fi
		fi

		db_update_network_interface "${_iface}" "${_c}" "0"

		[ -n "${_found}" ] && _lanip=`echo "${_found}"|cut -f"${_f2}" -d'|'`
		[ -n "${_lanip}" ] && _lanip=`echo "${_lanip}"|cut -s -f1 -d'/'`

		prompt_ipaddress "${_ipv}" "${_iface}" "${_lanip}"
		_lanip="${VAL}"

		get_netmask "${_ipv}" "${_iface}"
		_mask="${VAL}"

		local _ip=`echo "${_found}"|cut -f"${_f2}" -d'|'`
		if [ -n "${_ip}" ]
		then
			_mask=`echo "${_ip}"|cut -s -f2 -d'/'`
		fi

		prompt_netmask "${_ipv}" "${_iface}" "${_mask}"
		_mask="${VAL}"

		prompt_gateway "${_ipv}"
		_gatewayip="${VAL}"

		prompt_dnsserver "${_ipv}"
		_dnsserverip="${VAL}"

		db_update_network_interface \
			"${_iface}" "int_${_ipv}address" "${_lanip}/${_mask}"
		db_update_network_globalconfiguration \
			"gc_${_ipv}gateway" "${_gatewayip}"

		local _i=1
		local _ifs="${IFS}"
		IFS=","
		for _d in ${_dnsserverip}
		do
			local _col="gc_nameserver${_i}"
			if [ -n "${_d}" ]
			then
				db_update_network_globalconfiguration \
					"${_col}" "${_d}"
			fi

			_i=`expr "${_i}" + 1`
		done
		IFS="${_ifs}"
	fi
}

is_validip()
{
	local _protocol_family
	local _protocol

	_protocol_family="${1}"
	shift 1

	# ...
	# ...

	case "${_protocol}" in
		ipv4) [ "inet" = "${_protocol_family}" ] && return 0 ;;
		ipv6) [ "inet" = "${_protocol_family}" ] && return 0 ;;
	esac

	return 1
}
