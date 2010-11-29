#!/bin/sh

# quick script to make the database.

dir=$(dirname $0)
db=${1-/data/freenas-v1.db}

if [ -f ${db} ]; then
    rm ${db}
fi

python manage.py syncdb

python manage.py migrate network
python manage.py migrate services
python manage.py migrate sharing
python manage.py migrate storage
python manage.py migrate system

$dir/set_schema_defaults.sh $dir/schema.init $db
