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

configure_ipv6_dhcp()
{
}

get_ipv4_cidr_netmask()
{
	local _mask="${1}"
	if [ -z "${_mask}" ]
	then
		return 1
	fi

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
	if [ -z "${_mask}" ]
	then
		return 1
	fi

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
	if [ -z "${_mask}" ]
	then
		return 1
	fi

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
	fi

	export VAL
	return ${_res}
}

get_ipv4_dnsserver()
{
	local _config
	local _dnsserver

	unset VAL
	db_get_network_globalconfiguration
	_config="${VAL}"
	if [ -z "${_config}" ]
	then
		return 1
	fi

	unset VAL
	_dnsserver=`echo "${_config}"|cut -f6 -d'|'`
	if [ -z "${_dnsserver}" ]
	then
		return 1
	fi

	VAL="${_dnsserver}"
	export VAL

	return 0
}

get_ipv4_gateway()
{
	local _config
	local _gateway

	unset VAL
	db_get_network_globalconfiguration
	_config="${VAL}"
	if [ -z "${_config}" ]
	then
		return 1
	fi

	unset VAL
	_gateway=`echo "${_config}"|cut -f4 -d'|'`
	if [ -z "${_gateway}" ]
	then
		return 1
	fi

	VAL="${_gateway}"
	export VAL

	return 0
}

get_ipv4_netmask()
{
	local _iface="${1}"
	local _cidr="${2}"
	if [ -z "${_iface}" ]
	then
		return 1
	fi

	unset VAL
	local _res=0
	local _mask=`ifconfig "${_iface}"|grep 'inet '|awk '{ print $4 }'`
	if [ -z "${_mask}" ]
	then
		return 1
	fi

	if [ -n "${_cidr}" ]
	then
		get_ipv4_cidr_netmask "${_mask}"
	else
		get_ipv4_dotted_netmask "${_mask}"
	fi

	_res=$?
	export VAL
	return ${_res}
}

get_ipv4_address()
{
	local _iface="${1}"
	if [ -z "${_iface}" ]
	then
		return 1
	fi

	unset VAL
	local _res=0
	local _ip=`ifconfig "${_iface}"|grep 'inet '|awk '{ print $2 }'`
	if [ -z "${_ip}" ]
	then
		_res=1
	fi

	VAL="${_ip}"
	export VAL

	return ${_res}
}

get_ipv6_address()
{
	local _iface="${1}"
	if [ -z "${_iface}" ]
	then
		return 1
	fi

	unset VAL
	local _res=0
	local _ip=`ifconfig "${_iface}"|grep 'inet6 '|awk '{ print $2 }'`
	if [ -z "${_ip}" ]
	then
		_res=1
	fi

	VAL="${_ip}"
	export VAL

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

is_ipv4mask()
{
	local _mask="${1}"
	if [ -z "${_mask}" ]
	then
		return 1
	fi

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

		if [ "${_parts}" = "0" -o "${_parts}" -gt "4" ]
		then
			_res=1
		fi
		
		IFS="${_ifs}"

	else
		if [ "${_mask}" -ge "1" -a "${_mask}" -le "32" ]
		then
			_res=0
		fi
	fi

	return ${_res}
}

configure_ipv4_interface()
{
	local _args="${1}"
	local _iface=`echo "${_args}" | awk '{ print $1 }'`

	dialog --clear --yesno \
		"Do you want to use IPv4 DHCP for interface (${_iface})?" 5 75
	if [ "$?" = "0" ]
	then
		configure_ipv4_dhcp "${_iface}"

	else
		# Configure interface
		local _lanip
		local _found

		db_get_network_interface "${_iface}"
		_found="${VAL}"

		if [ -n "${_found}" ]
		then
			local _lanip
			local _tmpfile
			local _loop
			local _mask
			local _gatewayip
			local _dnsserverip

			local _dhcp=`echo "${_found}"|cut -f4 -d'|'`
			if [ "${_dhcp}" = "1" ]
			then
				get_ipv4_address "${_iface}"
				_lanip="${VAL}"

				if [ -z "${_lanip}" ]
				then
					_lanip=`echo "${_found}"|cut -f5 -d'|'|cut -s -f1 -d'/'`
				fi
			fi

			_tmpfile="/tmp/answer.txt"
			_loop=1

			while [ "${_loop}" = "1" ]
			do
				dialog --clear --inputbox "Enter new LAN IPv4 address." \
					8 35 "${_lanip}" 2>"${_tmpfile}"
				[ "$?" = "0" ] || exit 1

			    _lanip=`cat "${_tmpfile}"`
				rm -f "${_tmpfile}"

				# Is valid IP?
				if is_ipv4addr "${_lanip}"
				then
					_loop=0
				fi

			done


			get_ipv4_netmask "${_iface}"
			_mask="${VAL}"

			if [ -z "${_mask}" ]
			then
				local _ip=`echo "${_found}"|cut -f5 -d'|'`
				if [ -n "${_ip}" ]
				then
					_mask=`echo "${_ip}"|cut -s -f2 -d'/'`
				fi
			fi

			_loop=1
			while [ "${_loop}" = "1" ]
			do
				dialog --clear --inputbox "Enter new LAN subnet mask." \
					8 35 "${_mask}" 2>"${_tmpfile}"
				[ "$?" = "0" ] || exit 1

				_mask=`cat "${_tmpfile}"`
				rm -f "${_tmpfile}"

				# Is valid netmask?
				if is_ipv4mask "${_mask}"
				then
					_loop=0
				fi

				netmask_to_cidr "${_mask}"
				_mask="${VAL}"

			done

			get_ipv4_gateway
			_gatewayip="${VAL}"

			_loop=1
			while [ "${_loop}" = "1" ]
			do
				dialog --clear --inputbox "Enter IPv4 default gateway." \
					8 35 "${_gatewayip}" 2>"${_tmpfile}"
				[ "$?" = "0" ] || exit 1

				_gatewayip=`cat "${_tmpfile}"`
				rm -f "${_tmpfile}"

				# Is valid IP?
				if is_ipv4addr "${_gatewayip}"
				then
					_loop=0
				fi

			done


			get_ipv4_dnsserver
			_dnsserverip="${VAL}"

			_loop=1
			while [ "${_loop}" = "1" ]
			do
				dialog --clear --inputbox "Enter DNS IPv4 address." \
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
					if ! is_ipv4addr "${_d}"
					then
						_bad=`expr "${_bad}" + 1`
					fi
				done

				[ "${_bad}" = "0" ] && _loop=0
				IFS="${_ifs}"

			done

			db_update_network_interface \
				"${_iface}" "int_ipv4address" "${_lanip}/${_mask}"
			db_update_network_globalconfiguration \
				"gc_ipv4gateway" "${_gatewayip}"

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

		else

		fi

		
	fi
}

configure_ipv6_interface()
{
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
