#!/bin/sh

# quick script to make the database.

dir=$(dirname $0)
db=${1-/data/freenas-v1.db}

if [ -f ${db} ]; then
    mv ${db} "${db}.old"
fi

python manage.py syncdb --migrate --noinput
python manage.py createadmin
