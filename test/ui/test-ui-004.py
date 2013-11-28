#
# This program requires installation of the splinter
# library.  See: http://splinter.cobrateam.info/
#

from splinter import Browser
import json, getopt
import sys

test_config = None


def usage(argv):
    print "Usage:"
    print "    %s -f [JSON config file]" % argv[0]


# The following test:
#   (1) opens a web browser
#   (2) sets the default password

def main(argv):

    try:
        opts, args = getopt.getopt(sys.argv[1:], "f:")
    except getopt.GetoptError as err:
        sys.exit(2)

    global test_config
    config_file_name = None

    for o, a in opts:
        if o == "-f":
            config_file_name = a
        else:
            assert False, "unhandled option"

    if config_file_name is None:
        usage(argv)
        sys.exit(1)

    config_file = open(config_file_name, "r")
    test_config = json.load(config_file)

    browser = Browser()
    browser.visit(test_config['url'])
    browser.find_by_id('id_password').fill(test_config['password'])
    browser.find_by_id('id_confirm_password').fill(test_config['password'])
    browser.find_by_id('dijit_form_Button_0_label').click()
    browser.quit()
   

if __name__ == "__main__":
    main(sys.argv)
