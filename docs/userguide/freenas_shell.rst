.. index:: Shell
.. _Shell:

Shell
=====

The FreeNAS® GUI provides a web shell, making it convenient to run command line tools from the web browser as the *root* user. 
The link to Shell is the fourth entry from the bottom of the menu tree. In Figure 16a, the link has been clicked and Shell is open.

**Figure 16a: Web Shell**

.. image:: images/shell1.png

By default, the shell opens the FreeNAS® CLI. The default shell can be changed for that user in :menuselection:`Account --> Users`. Alternately, type :command:`shell` to switch to
the Bash shell.

To change the size of the shell, click the *80x25* drop-down menu and select a different size.

To copy text from shell, highlight the text, right-click, and select "Copy" from the right-click menu. To paste into the shell, click the "Paste" button,
paste the text into the box that opens, and click the "OK" button to complete the paste operation.

While you are in Shell, you will not have access to any of the other GUI menus. If you need to have access to a prompt while using the GUI menus, use
:ref:`tmux` instead as it supports multiple shell sessions and the detachment and reattachment of sessions.