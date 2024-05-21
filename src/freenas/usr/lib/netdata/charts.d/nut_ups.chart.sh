source /usr/lib/netdata/charts.d/nut.chart.sh


ups_config=''

get_ups_config(){
  if [ -e /var/db/system/netdata/ups_info.json ]; then
    run -t $nut_timeout cat /var/db/system/netdata/ups_info.json;
  else
    run -t $nut_timeout echo "";
  fi
}

get_ups_remote(){
  remote_addr=$(echo "$ups_config" | jq '.remote_addr')
  run -t $nut_timeout echo "${remote_addr:1:-1}"
}

nut_get_all() {
  if [ $(ps -aux | grep upsmon | wc -l) -le 1 ]; then
    run -t $nut_timeout echo "ix-dummy-ups";
    return 0
  fi

  if [ -z $(get_ups_remote) ]; then
      run -t $nut_timeout upsc -l || echo "ix-dummy-ups";
  else
    run -t $nut_timeout upsc -l $(get_ups_remote) || echo "ix-dummy-ups";
  fi
}

nut_get() {
  if [ $1 == "ix-dummy-ups" ]; then
    return 0;
  fi
  remote_addr=''
  if [ ! -z $(get_ups_remote) ]; then
    remote_addr="@$(get_ups_remote)"
  fi

  run -t $nut_timeout upsc "$1$remote_addr"

  if [ "${nut_clients_chart}" -eq "1" ]; then
    run -t $nut_timeout upsc -c $1$remote_addr | wc -l
  fi
}



nut_ups_check() {

  # this should return:
  #  - 0 to enable the chart
  #  - 1 to disable the chart

  local x

  require_cmd upsc || return 1

  ups_config="$(get_ups_config)"
  nut_ups="$(nut_get_all)"
  nut_names=()
  nut_ids=()
  for x in $nut_ups; do
    nut_get "$x" > /dev/null
    # shellcheck disable=SC2181
    if [ $? -eq 0 ]; then
      if [ -n "${nut_names[${x}]}" ]; then
        nut_ids[$x]="$(fixid "${nut_names[${x}]}")"
      else
        nut_ids[$x]="$(fixid "$x")"
      fi
      continue
    fi
    error "cannot get information for NUT UPS '$x'."
  done

  if [ ${#nut_ids[@]} -eq 0 ]; then
    # shellcheck disable=SC2154
    error "Cannot find UPSes - please set nut_ups='ups_name' in $confd/nut.conf"
    return 1
  fi

  return 0
}

nut_ups_create() {
  # create the charts
  nut_create
}

nut_ups_update() {
  # the first argument to this function is the microseconds since last update
  # pass this parameter to the BEGIN statement (see below).

  # do all the work to collect / calculate the values
  # for each dimension
  # remember: KEEP IT SIMPLE AND SHORT
  ups_config="$(get_ups_config)"
  nut_ups_check
  nut_ups_create
  nut_update $@
}
