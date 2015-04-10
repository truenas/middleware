#!/usr/local/bin/python
import sys, getopt, re
from redmine import Redmine, exceptions

def main(argv):
    key = ''
    project = ''
    try:
        opts, args = getopt.getopt(argv,"hk:p:", ["key=","project="])
    except getopt.GetoptError:
        print 'create_redmine_changelog.py -k <key> -p <project>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print 'create_version.py -k <key> -v <version> -p <project> -d <description>'
            sys.exit(2)
        elif opt in ("-k", "--key"):
            key = arg
        elif opt in ("-p", "--project"):
            project = arg
    if key == '':
        print '<key> cannot be blank'
        sys.exit(2)
    if project == '':
        print '<project> cannot be blank'
        sys.exit(2)
   
    rm = Redmine('https://bugs.freenas.org', key=key) 

    statuses = rm.issue_status.all()
    for status in statuses:
        if str(status) == "Ready For Release":
	    ready = status
	    break

    if ready:
        issues = rm.issue.filter(status_id=ready.id)
    else:
        print 'Ready For Release status does not exist or server is unreachable'
        sys.exit(2)

    entrytext = ''

    for issue in reversed(issues):
        skip = False
        if project.lower() == 'freenas' and str(issue.project).lower() == 'truenas':
            skip = True
        else:
            for field in issue.custom_fields:
                if str(field) == "ChangeLog Entry":
                    if field.value:
                        if not 'hide this' in field.value.lower():
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
                    entrytext = re.sub('\n','\n\t\t\t', entrytext)
                    print "#" + str(issue.id) + "\t" + str(issue.tracker) + "\t" + str(issue.priority) + "\t" + entrytext
                else:
                    entrytext = re.sub('\n','\n\t', entrytext)
                    print "#" + str(issue.id) + "\t" + entrytext
        
if __name__ == "__main__":
   main(sys.argv[1:])
