#!/usr/local/bin/python

import sys
import getopt
import re
import unicodedata
from redmine import Redmine, exceptions


def main(argv):
    key = ''
    project = ''
    try:
        opts, args = getopt.getopt(argv, "hk:p:", ["key=", "project="])
    except getopt.GetoptError:
        print("create_redmine_changelog.py -k <key> -p <project>")
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print("create_version.py -k <key> -v <version> -p <project> -d <description>")
            sys.exit(2)
        elif opt in ("-k", "--key"):
            key = arg
        elif opt in ("-p", "--project"):
            project = arg
    if key == '':
        print("<key> cannot be blank")
        sys.exit(2)
    if project == '':
        print("<project> cannot be blank")
        sys.exit(2)

    bugs = 'https://bugs.freenas.org'

    rm = Redmine(bugs, key=key)

    statuses = rm.issue_status.all()
    for status in statuses:
        if str(status) == "Ready For Release":
            ready = status
            break

    if ready:
        issues = rm.issue.filter(status_id=ready.id)
    else:
        print("Ready For Release status does not exist or server is unreachable")
        sys.exit(2)

    entrytext = ''

    for issue in reversed(issues):
        skip = False
        try:
            if str(issue.fixed_version) != "SU Candidate":
                sys.stderr.write(
                    "WARNING: {0}/issues/{1} is set to {2} not to SU Candidate\n".format(
                        bugs, issue.id, issue.fixed_version)
                )
                skip = True
        except exceptions.ResourceAttrError:
            sys.stderr.write(
                "WARNING: {0}/issues/{1} target version is not set\n".format(bugs, issue.id)
            )
            skip = True

        if project.lower() == 'freenas' and str(issue.project).lower() == 'truenas':
            skip = True
        else:
            for field in issue.custom_fields:
                if str(field) == "ChangeLog Entry":
                    if field.value:
                        if 'hide this' not in field.value.lower():
                            if project.lower() == 'truenas' and 'freenas only' in field.value.lower():
                                skip = True
                            else:
                                entrytext = field.value
                        else:
                            skip = True
                    else:
                        entrytext = issue.subject
            if not skip:
                entrytext = re.sub('[f|F][r|R][e|E][e|E][n|N][a|A][s|S]\s*[o|O][n|N]|[l|L][y|Y]:?', '', entrytext).strip()
                if project.lower() == 'freenas':
                    entrytext = re.sub('\n', '\n\t\t\t', entrytext)
                    try:
                        print("#{0}\t{1}\t{2}\t{3}".format(issue.id, issue.tracker, issue.priority, entrytext))
                    except UnicodeError:
                        entrytext = unicodedata.normalize('NFKD', entrytext).encode('ascii', 'ignore')
                        print("#{0}\t{1}\t{2}\t{3}".format(issue.id, issue.tracker, issue.priority, entrytext))
                else:
                    entrytext = re.sub('\n', '\n\t', entrytext)
                    print("#{0}\t{1}".format(issue.id, entrytext))


if __name__ == "__main__":
    main(sys.argv[1:])
