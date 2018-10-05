#!/bin/sh
# ---------------------------------
# Simple script to fetch instantaneous system statistics and report them as a JSON block
# This can run either as user or as root
# Written by Ken Moore (ken@ixsystems.com) Aug 31, 2018
# ---------------------------------

#time_t time (seconds since epoch)
_time=`date -j +%s`

_output=""
append_json_to_object(){
  #Inputs: 
  #  $1 - name of object
  #  $2 - JSON value for object
  if [ -n "${_output}" ] ; then
    #Need to add a comma between this field and the previous
    _output="${_output},"
  fi
  _output="${_output} \"$1\": $2"
}

gstat_to_json(){
  #Since gstat does not have a libxo output option, need to convert to JSON manually
  #Still sets the "_tmp" variable as output
  _i=0
  _max_i=10 #10 columns in output as of 8/31/18 (Ken Moore)
  local _out=$( gstat -bp |
  while read line
  do
    #Output Fields:
    _test=`echo "${line}" | cut -w -f ${_max_i}`
    if [ -z "${_test}" ] ; then continue;
    elif [ "${_test}" = "Name" ] ; then
      #Got the labels at the top - save this for later
      _labels="${line}"
      continue
    fi
    if [ ${_i} -ne 0 ] ; then printf ", "; 
    else _i=1; fi
    #Put the information into a JSON object
    _out="{"
    for i in `jot ${_max_i} 1`
    do
      _lab=`echo ${_labels} | cut -w -f ${i}`
      _val=`echo ${line} | cut -w -f ${i}`
      if [ "${_lab}" = "Name" ] ; then
        _val=`echo ${_val} | sed 's|%20| |g'`
        _out="${_out}\"${_lab}\":\"${_val}\""
      else
        _out="${_out}\"${_lab}\":${_val}"
      fi
      if [ ${i} -lt ${_max_i} ] ; then
        _out="${_out},"
      else
        printf "${_out}}" 
      fi
    done
  done 
  )
  _tmp="[${_out}]"
}

ifstat_to_json(){
  _tmp=""
  local _out=$( ifstat -a -T 0.1 1 |
  while read line
  do
    # First line is interface labels
    if [ -z "${_ifaces}" ] ; then
      _ifaces="${line}"
      #Always 2 entries per interface in lower lines
      inum=`echo ${_ifaces} | wc -w | tr -d '[:space:]'`
      continue
    fi
    if [ -z "${_labels}" ] ; then
      _labels="${line}"
      continue
    fi
    #echo "Got Labels: ${_labels}"
    #echo "Got Interfaces: ${_ifaces}"
    for i in `jot ${inum} 1`
    do
      iface=`echo ${_ifaces} | cut -w -f ${i}`
     if [ -n "${_tmp}" ] ; then
        _tmp="${_tmp}, "
     fi
     _tmp="${_tmp}{ \"name\" : \"${iface}\","
      _num=`expr ${i} - 1`
      _num=`expr ${_num} \* 2`
      _num=`expr ${_num} + 1`
      _numend=`expr ${_num} + 1`
      label=`echo ${_labels} | cut -w -f ${_num}-${_numend} | sed $'s/\t/ /g'`
      value=`echo ${line} | cut -w -f ${_num}`
      _tmp="${_tmp}\"${label}\" : \"${value}\","
      _num=`expr ${_num} + 1`
      _numend=`expr ${_num} + 2`
      label=`echo ${_labels} | cut -w -f $(expr ${_num} + 1)-${_numend} | sed $'s/\t/ /g'`
      value=`echo ${line} | cut -w -f ${_num}`
      _tmp="${_tmp}\"${label}\" : \"${value}\" }"
    done #interface loop
    echo "${_tmp}"
  done #read loop
  )
  _tmp="[${_out}]"
}

get_cpu_temp_to_json(){
  _tmp=""
  local _out=$(sysctl -q dev.cpu. | grep temperature | 
  while read line
  do
    num=`echo "${line}" | cut -d . -f 3`
    val=`echo "${line}" | cut -w -f 2 | cut -d C -f 1` #need to cut the "C" off the end of the value as well
    #Now echo out that variable/value pair
    if [ -n "${num}" ] && [ -n "${val}" ] ; then
      echo ",\"${num}\":${val}"
    fi
  done
  )
  if [ -n "${_out}" ] ; then
    _tmp="{\"units\":\"C\"${_out}}"
  fi
}

#Get the memory per kernel zone
_tmp=`vmstat -z --libxo json`
if [ -n "${_tmp}" ] ; then
  append_json_to_object "memory_zone" "${_tmp}"
fi
#Get the memory summary
_tmp=`vmstat -s --libxo json`
if [ -n "${_tmp}" ] ; then
  append_json_to_object "memory_summary" "${_tmp}"
fi
#Get the CPU system status (broken down by CPU core)
_tmp=`vmstat -P --libxo json`
if [ -n "${_tmp}" ] ; then
  append_json_to_object "vmstat_summary" "${_tmp}"
fi
#Get the CPU temperatures
get_cpu_temp_to_json
if [ -n "${_tmp}" ] ; then
  append_json_to_object "cpu_temperatures" "${_tmp}"
fi
#disk I/O stats
gstat_to_json
if [ -n "${_tmp}" ] ; then
  append_json_to_object "gstat_summary" "${_tmp}"
fi
#network stats
_tmp=`netstat -i -s --libxo json`
if [ -n "${_tmp}" ] ; then
  append_json_to_object "netstat_summary" "${_tmp}"
fi
if [ -e "/usr/local/bin/ifstat" ] ; then
  ifstat_to_json
  if [ -n "${_tmp}" ] ; then
    append_json_to_object "network_usage" "${_tmp}"
  fi
fi

#Append the timestamp to the output
append_json_to_object "time_t" "${_time}"
echo "{${_output}}"
