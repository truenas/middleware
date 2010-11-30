#!/bin/sh

# quick script to make the database.

dir=$(dirname $0)
db=${1-/data/freenas-v1.db}

if [ -f ${db} ]; then
    rm ${db}
fi

python manage.py syncdb --migrate

$dir/set_schema_defaults.sh $dir/schema.init $db
