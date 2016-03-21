#!/usr/local/bin/python

import sys
import getopt
import re
from datetime import date, datetime
from redmine import Redmine, exceptions


def main(argv):
    key = ''
    vers = ''
    descrpt = ''
    try:
        opts, args = getopt.getopt(argv, "hk:v:d:p:", ["key=", "version=", "description=", "project="])
    except getopt.GetoptError:
        print("create_version.py -k <key> -v <version> -d <description> -p <project>")
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print("create_version.py -k <key> -v <version> -d <description> -p <project>")
            sys.exit(2)
        elif opt in ("-k", "--key"):
            key = arg
        elif opt in ("-v", "--version"):
            vers = arg
        elif opt in ("-d", "--description"):
            descrpt = arg
        elif opt in ("-p", "--project"):
            project = arg
    if key == '':
        print("<key> cannot be blank")
        sys.exit(2)
    if vers == '':
        print("<version> cannot be blank")
        sys.exit(2)
    if project == '':
        print("<project> cannot be blank")
        sys.exit(2)
    creation_date = re.match(r".*(\d{4})(\d{2})(\d{2})\d{4}", vers)
    redmine = Redmine('https://bugs.freenas.org', key=key)
    rm_project = redmine.project.get(project)
    version = redmine.version.new()
    version.project_id = rm_project.id
    version.name = vers
    version.description = descrpt
    version.status = 'closed'
    version.sharing = 'none'
    if creation_date:
        version.due_date = date(int(creation_date.group(1)), int(creation_date.group(2)), int(creation_date.group(3)))
    else:
        version.due_date = date(datetime.now().year, datetime.now().month, datetime.now().day)
    result = ''
    try:
        result = version.save()
    except exceptions.ValidationError:
        print("Could not create version")
    except exceptions.AuthError:
        print("Error authenticating with server")
    if result:
        print("Version {0} successfully created".format(vers))
    else:
        print("Error creating version {0}".format(vers))

if __name__ == "__main__":
    main(sys.argv[1:])
