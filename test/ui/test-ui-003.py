#
# This program requires installation of the splinter
# library.  See: http://splinter.cobrateam.info/
#

from splinter import Browser
import json, getopt
import sys
import time

test_config = None


def usage(argv):
    print "Usage:"
    print "    %s -f [JSON config file]" % argv[0]


# The following test opens a web browser.
#   (1) opens a web browser
#   (2) logs in

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
    e = browser.find_by_xpath("//div[@id='treeNode_account']/div/span")
    e.click()
    e = browser.find_by_xpath("//div[@id='treeNode_account.AdminAccount']/div/span")
    e.click()
    e = browser.find_by_xpath("//div[@id='treeNode_account.AdminAccount.ChangePass']/div/span[3]/span[2]")
    time.sleep(1)
    e.click()
    browser.find_by_id('id_new_password').fill(test_config['password'])
    browser.find_by_id('id_new_password2').fill(test_config['password'])
    browser.find_by_id('btn_PasswordChangeForm_Ok_label').click()

if __name__ == "__main__":
    main(sys.argv)
