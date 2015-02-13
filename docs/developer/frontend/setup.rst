.. highlight:: javascript
   :linenothreshold: 5

Set up your Development Environment
===================================

Required Software
-----------------

You will need some tools installed in your development environment to
get started. The initialization script will tell you if you're missing
certain tools, and simply fail if you're missing others. You won't be
able to proceed without them all.

Required Tools: \* ``which`` \* ``ping`` \* ``ssh`` \* ``rsync`` \*
``tar`` \* ``scp`` \* ```git`` <http://git-scm.com/downloads>`__ \*
`python 2.7 <https://www.python.org/downloads/>`__ \* a C++ compiler \*
```node`` <http://nodejs.org/>`__ \* ``npm`` (Node Package Manager)

FreeBSD Development Environments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

On FreeBSD, use ``pkg install`` to install any software you're missing
(superuser privileges may be required to install software). For example,
``sudo pkg install python27`` will install python 2.7 using root
privileges. Installing npm will also install node as a dependency. To be
certain npm is up to date after installation, run ``npm update npm -g``.

Mac OS X
~~~~~~~~

An easy way to install node and npm on Mac OS X is
`Homebrew <http://brew.sh/>`__. To install node with homebrew, run
``brew install node``.

XCode (available in the App Store) is the recommended source of a C++
compiler for Max OS X.

Windows Development Environments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Windows users will need `Cygwin <http://cygwin.com/install.html>`__ to
get most of the required environment tools. The only two non-default
packages needed for Cygwin are rsync and openssh.

You may have to add the Cygwin path to the windows path manually. To do
this on Windows 7, go to the "System" control panel item and click on
"Advanced System Settings" in the left column. Next, go to the
"Advanced" panel and click "Environment Variables". From there, find
"Path" in the "System Variables" list and append a semicolon followed by
your Cygwin binary path, by default ``C:\cygwin64\bin``.

If you don't already have an ssh keypair you wish to use, run the
command ``ssh-keygen`` from the command prompt. By default, the keys
will be in the Cygwin home folder - you may wish to move them to make
the path to them easier to enter later.

For Windows, the tested source of a C++ compiler is `Microsoft Visual
Studio
2010 <http://msdn.microsoft.com/en-us/library/dd831853(v=vs.100).aspx>`__.

Follow the setup instructions in a windows command prompt in
administrator mode, and start a new administrator command prompt after
any software installation in order for them to work. Do NOT use the
Cygwin console.

The standard windows installer for node also includes npm.

Run Install Scripts
~~~~~~~~~~~~~~~~~~~

Once you have npm and node installed, run
``npm install forever grunt grunt-cli bower -g``. This will install the
rest of the tools used to make FreeNAS initialization and further
development possible. Next, run ``npm install`` and ``bower install`` in
that order from the directory you're using for your source repository.

Set up a Development target
---------------------------

UI development works by pushing all changes immediately to a target
FreeNAS instance. This instance should be dedicated solely to FreeNAS
development and not contain any important data nor support any services
in actual use. Additionally, FreeNAS development target instances cannot
be shared - unpredictable results may occur if two or more developers
attempt to use the same FreeNAS instance as a target.

Requirements for FreeNAS Instance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A FreeNAS instance to be used as a target for FreeNAS development must
be configured as follows:

-  Has a volume and a dataset using Unix permissions
-  Has rsync enabled
-  Has ssh enabled
-  Has a public key installed for the FreeNAS root user, with the
   corresponding private key in your development environment (not
   required, but recommended.)

Initialize Your FreeNAS Instance and Development Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Begin this process only once you have completed setup of your
development environment and your target FreeNAS instance is configured
as described. To begin the FreeNAS initialization process, navigate to
the directory on your development environment where you're keeping your
local source and run the command ``grunt``. A series of scripts will
run, first requesting information about how to connect to your FreeNAS
instance and then sanity checking and installing all the necessary
software to your FreeNAS instance. Once this completes, run ``grunt``.
This will also install the current version of the FreeNAS GUI webapp to
your FreeNAS instance, and make it accessible by default on port 4000.
