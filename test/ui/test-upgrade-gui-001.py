#
# This program requires installation of the splinter
# library.  See: http://splinter.cobrateam.info/
#
# The following test opens a web browser.
#   (1) opens a web browser
#   (2) logs into the FreeNAS UI as the root user
#   (3) clicks on the System -> Settings -> Advanced -> Firmware Upgrade
#   (4) Uploads an image for upgrade

from splinter import Browser
import json, getopt
import re
import sys
import time

test_config = None


def usage(argv):
    print "Usage:"
    print "    %s -f [JSON config file]" % argv[0]

def get_sha256_checksum_from_file(file):
    f = open(file, "r")
    s = f.readline()
    f.close()

    checksum = re.sub("^.* ", "", s)
    return checksum

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

    # log in
    browser.find_by_id('id_username').fill(test_config['username'])
    browser.find_by_id('id_password').fill(test_config['password'])
    browser.find_by_id('dijit_form_Button_0_label').click()

    # Enable SSH
    browser.find_by_id('menuBar_System').click()
    browser.find_by_id('content_tablist_systemTab_Settings').click()
    browser.find_by_id('dijit_layout_TabContainer_0_tablist_dijit_layout_ContentPane_1').click()
    browser.find_by_id('btn_AdvancedForm_FwUpdate_label').click()
    browser.find_by_id('btn_FirmwareTemporaryLocationForm_Ok_label').click()

    e = browser.find_by_id('id_1-firmware')
    e.fill(test_config['upgrade_file'])
    e = browser.find_by_id('id_1-sha256')
    sha256_checksum = get_sha256_checksum_from_file(test_config['upgrade_file'] + ".sha256.txt") 
    e.fill(sha256_checksum)

    browser.find_by_id('btn_FirmwareUploadForm_Ok_label').click()

    browser.quit()

if __name__ == "__main__":
    main(sys.argv)
