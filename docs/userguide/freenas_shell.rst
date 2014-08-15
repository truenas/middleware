:orphan:

Shell
=====

Beginning with version 8.2.0, the FreeNAS® GUI provides a web shell, making it convenient to run command line tools from the web browser as the *root* user.
The link to Shell is the third entry from the bottom of the menu tree. In Figure 16a, the link has been clicked and Shell is open.

The prompt indicates that the current user is *root*, the hostname is
*freenas*, and the current working directory is :file:`~`
(*root*'s home directory).

To change the size of the shell, click the *80x25* drop-down menu and select a different size.

To copy text from shell, highlight the text, right-click, and select "Copy" from the right-click menu. To paste into the shell, click the "Paste" button,
paste the text into the box that opens, and click the "OK" button to complete the paste operation.

**Figure 16a: Web Shell**

|Figure16a_png|

While you are in Shell, you will not have access to any of the other GUI menus. If you are using Shell for troubleshooting purposes and need to leave the
Shell in order to modify a configuration, click the "x" in the window's upper right corner. The next time you enter Shell, you will return to your last session.
When you are finished using Shell, type :command:`exit` to leave the session completely.

Shell provides history (use your up arrow to see previously entered commands and press :kbd:`Enter` to repeat the currently displayed command) and tab
completion (type a few letters and press tab to complete a command name or filename in the current directory).

.. note:: not all of Shell's features render correctly in Chrome. Firefox is the recommended browser for using Shell.

Due to the embedded nature of FreeNAS®, some FreeBSD components are missing and noticeable in Shell. For example, man pages are not included; however, a link
to the online FreeBSD man pages is available from Help. Most FreeBSD command line utilities should be available in Shell. Additional troubleshooting utilities
that are provided by FreeNAS® are described in Useful Command Line Utilities.