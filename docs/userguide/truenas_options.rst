:orphan:

Additional Options
------------------

This section covers the remaining miscellaneous options available from the TrueNAS® graphical administrative interface.


Display System Processes
~~~~~~~~~~~~~~~~~~~~~~~~

If you click Display System Processes, a screen will open showing the output of
`top(1) <http://www.freebsd.org/cgi/man.cgi?query=top>`_. An example is shown in Figure 12.1a.

**Figure 12.1a: System Processes Running on TrueNAS®**

|10000000000001F70000019B91B24E55_png|

.. |10000000000001F70000019B91B24E55_png| image:: images/processes.png
    :width: 6.0598in
    :height: 3.8055in

The display will automatically refresh itself. Simply click the X in the upper right corner to close the display when you are finished. Note that the display
is read-only, meaning that you won't be able to issue a :command:`kill` command within it.


Shell
~~~~~

The TrueNAS® GUI provides a web shell, making it convenient to run command line tools from the web browser as the *root* user. The link to Shell is the third
entry from the bottom of the menu tree. In Figure 12.2a, the link has been clicked and Shell is open.

The prompt indicates that the current user is *root*, the hostname is
*freenas*, and the current working directory is :file:`~`
(*root*'s home directory).

To change the size of the shell, click the *80x25* drop-down menu and select a different size.

To copy text from shell, highlight the text, right-click, and select Copy from the right-click menu. To paste into the shell, click the "Paste" button, paste
the text into the box that opens, and click the OK button to complete the paste operation.

**Figure 12.2a: Web Shell**

|100000000000036900000273BD5795E8_png|

.. |100000000000036900000273BD5795E8_png| image:: images/shell.png
    :width: 6.9252in
    :height: 4.9319in

While you are in Shell, you will not have access to any of the other GUI menus. If you are using Shell for troubleshooting purposes and need to leave the
Shell in order to modify a configuration, click the "x" in the window's upper right corner. The next time you enter Shell, you will return to your last
session. When you are finished using Shell, type :command:`exit` to leave the session completely.

Shell provides history (use your up arrow to see previously entered commands and press enter to repeat the currently displayed command) and tab completion
(type a few letters and press tab to complete a command name or filename in the current directory).

.. note:: not all of Shell's features render correctly in Chrome. Firefox is the recommended browser for using Shell.

Due to the embedded nature of TrueNAS®, some FreeBSD components are missing and noticeable in Shell. For example, man pages are not included; however,
FreeBSD man pages are available
`online <http://www.freebsd.org/cgi/man.cgi>`_. Most FreeBSD command line utilities should be available in Shell.

Reboot
~~~~~~

If you click "Reboot", you will receive the warning message shown in Figure 12.3a and your browser color will change to red to indicate that you have selected
an option that will negatively impact users of the TrueNAS® system.

.. note:: if any volumes are encrypted, make sure that you have set the passphrase and have copies of the encryption key and the latest recovery key as
   described in `Creating an Encrypted`_ before performing a reboot. 
   **Without these, you will not be able to unlock the encrypted volume as described in `Unlocking an Encrypted Volume`_ after the reboot.**

**Figure 12.3a: Reboot Warning Message**

|10000000000002BE000001A574FBAE48_png|

.. |10000000000002BE000001A574FBAE48_png| image:: images/reboot.png
    :width: 5.8984in
    :height: 3.5083in

If a scrub or resilver is in progress when a reboot is requested, an additional warning will ask you to make sure that you wish to proceed. In this case, it
is recommended to "Cancel" the reboot request and to periodically run :command:`zpool status` from `Shell`_ until it is verified that the scrub or resilver
process is complete. Once complete, the reboot request can be re-issued.

Click the "Cancel" button if you wish to cancel the reboot request. Otherwise, click the Reboot button to reboot the system. Rebooting the system will
disconnect all clients, including the web administration GUI. The URL in your web browser will change to add */system/reboot/* to the end of the IP address.
Wait a few minutes for the system to boot, then use your browser's back button to return to the TrueNAS® system's IP address. If all went well, you should
receive the GUI login screen. If the login screen does not appear, you will need physical access to the TrueNAS® system's monitor and keyboard so that you
can determine what problem is preventing the system from resuming normal operation.

Shutdown
~~~~~~~~

If you click "Shutdown", you will receive the warning message shown in Figure 12.4a and your browser color will change to red to indicate that you have
selected an option that will negatively impact users of the TrueNAS® system.

.. note:: if any volumes are encrypted, make sure that you have set the passphrase and have copies of the encryption key and the latest recovery key as
   described in `Creating an Encrypted`_ before performing a reboot. 
   **Without these, you will not be able to unlock the encrypted volume as described in `Unlocking an Encrypted Volume`_ after the reboot.**

**Figure 12.4a: Shutdown Warning Message**

|10000000000002C10000019740B2F0FB_png|

.. |10000000000002C10000019740B2F0FB_png| image:: images/shutdown.png
    :width: 5.9244in
    :height: 3.3917in

If a scrub or resilver is in progress when a shutdown is requested, an additional warning will ask you to make sure that you wish to proceed. In this case, it
is recommended to "Cancel" the shutdown request and to periodically run :command:`zpool status` from `Shell`_ until it is verified that the scrub or resilver
process is complete. Once complete, the shutdown request can be re-issued.

Click the "Cancel" button if you wish to cancel the shutdown request. Otherwise, click the "Shutdown" button to halt the system. Shutting down the system will
disconnect all clients, including the web administration GUI, and will power off the TrueNAS® system. You will need physical access to the TrueNAS® system
in order to turn it back on.

Help
~~~~

The Help button in the upper right corner provides a pop-up menu containing hyperlinks to the following TrueNAS® support resources:

*   the link to open a support ticket

*   the link to the TrueNAS® knowledge base

*   the email address of the support team

Creating a Support Ticket
^^^^^^^^^^^^^^^^^^^^^^^^^

As an iXsystems customer, you have access to the resources available at
`http://support.ixsystems.com <http://support.ixsystems.com/>`_, shown in Figure 12.5a.

**Figure 12.5a: iXsystems Support Website**

|1000000000000458000002652BE624B1_png|

.. |1000000000000458000002652BE624B1_png| image:: images/support.png
    :width: 6.9252in
    :height: 3.7492in

The support website provides some knowledge base articles. If the support issue is not addressed by the TrueNAS® Administrator Guide or a knowledge base
article, click the "Submit a Ticket" hyperlink, then click TrueNAS® so that your ticket can be routed to a TrueNAS® support representative.

In the "Submit a Ticket" screen, select "TrueNAS" then click the "Next" button.

You will then be prompted to fill in your "Contact Information", "System Details", and a description of the issue. Use a "Subject" line that summarizes the
support issue.

The "Message Details" should contain a summary of how to recreate the problem, as well as any applicable error messages or screenshots. Use the "Upload Files"
button to attach a log file or screenshot. If the issue is related to a configuration, upload the file that is created by going to `System -> Advanced -> Save
Debug`.

When finished, input the captcha information and click the "Submit" button. A message will indicate that the ticket has been submitted and has been issued a
Ticket ID. An email confirmation will also be sent, indicating the Ticket ID and providing a hyperlink to check the status of or to reply to the ticket.

A login account is not required to submit a ticket. However, a login is required in order to view your submitted tickets. If you do not have a login account,
click "Register" to create one. The registration process will ask for your name, email address, a password, and to verify a captcha image. A registration
email will be sent to the provided email address; you will not be able to login until you follow the link in the email to validate your account.

To view the status of your tickets, click the "View Tickets" tab while logged in. In addition to the status, you can view any comments by support staff as
well as click a ticket's Post Reply button in order to respond to a comment or to provide additional requested information.

Log Out
~~~~~~~

To log out of the TrueNAS® GUI, simply click the "Log Out" button in the upper right corner. You will immediately be logged out. An informational message
will indicate that you are logged out and will provide a hyperlink which you can click on to log back in. When logging back in, you will be prompted for the
*root* password.

Alert
~~~~~

TrueNAS® provides an alert system to provide a visual warning of any conditions that require administrative attention. The "Alert" button in the far right
corner will flash red when there is an outstanding alert. In the example alert shown in Figure 12.7a. one of the disks in a ZFS pool is offline which has
degraded the state of the pool.

**Figure 12.7a: Example Alert Message**

|10000000000001860000009EEEECF771_png|

.. |10000000000001860000009EEEECF771_png| image:: images/alert.png
    :width: 4.0618in
    :height: 1.6453in

Informational messages will have a green "OK" while messages requiring attention will be listed as a red "CRITICAL". CRITICAL messages will also be emailed to
the root user account. If you are aware of a critical condition but wish to remove the flashing alert until you deal with it, uncheck the box next to that
message.

Behind the scenes, an alert script checks for various alert conditions, such as volume and disk status, and writes the current conditions to
:file:`/var/tmp/alert`. A javascript retrieves the current alert status every 5 minutes and will change the solid green alert icon to flashing red if a new
alert is detected. Some of the conditions that trigger an alert include:

*   UPS ONBATT/LOWBATT event

*   ZFS pool status changes from HEALTHY

*   the system is unable to bind to the WebGUI Address set in `System --> Settings --> General`

*   the system can not find an IP address configured on an iSCSI portal

