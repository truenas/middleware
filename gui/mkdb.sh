#!/bin/sh

# quick script to make the database.

dir=$(dirname $0)
db=${1-/data/freenas-v1.db}

python manage.py syncdb << __EOF__
yes
admin
root@freenas.local
freenas
freenas
__EOF__

$dir/set_schema_defaults.sh $dir/schema.init $db
