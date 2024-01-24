source /usr/lib/netdata/charts.d/nut.chart.sh

nut_get_all() {
  run -t $nut_timeout upsc -l || echo "ix-dummy-ups"
}

nut_ups_check() {

  # this should return:
  #  - 0 to enable the chart
  #  - 1 to disable the chart

  local x

  require_cmd upsc || return 1

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
  nut_ups_check
  nut_ups_create
  nut_update $@
}
