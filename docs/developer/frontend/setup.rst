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

Required Tools:
  * ``which``
  * ``ping``
  * ``ssh``
  * ``rsync``
  * ``tar``
  * ``scp``
  * A C++ compiler
  * ``node``
  * ``npm``

All environemnts will require superuser or Administrator permissions
for setup and development.

FreeBSD Development Environments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

On FreeBSD, use ``sudo pkg install`` to install any software you're missing.
FreeBSD 10 is strongly recommended, as this will make it more likely that
dependency versions will match and will also allow the same system to be used
for frontend development and compiling the whole system.

In FreeBSD, key tools will be installed from a terminal:
  * ``npm`` must be installed with ``sudo pkg install npm`` This will also install
    ``node`` as a dependency. To be certain npm is up to date, run ``sudo npm update npm -g``
    after the install is complete.

Mac OS X Development Environments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The key tools for Mac OS X are available with graphical installers:
  * XCode (available in the App Store) is the recommended source of a C++
    compiler for Max OS X. Simply search for '"xcode" to find it.
  * ``node`` is available at `Nodejs.org <http://nodejs.org/>`_. This installer
    will also install ``npm``. To ensure that npm is up to date, run
    ``sudo npm update -g npm`` after the install is complete.
  * ``git`` is available at `git-scm.org <http://git-scm.com/downloads>`_.

Windows Development Environments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Windows is not a fully supported development environment.
Only Windows 7 and later are even remotely supported.**

The key tools for Windows are available with graphical installers:
  * Microsoft Visual Studio 2010 is the most tested source of a C++ compiler
    Windows. It is available from `Microsoft Visual Studio 2010
    <http://msdn.microsoft.com/en-us/library/dd831853(v=vs.100).aspx>`_.
  * Python 2.7 is needed for interpreting of Python code. Best source of Windowse
    package would be `The Official Python Website <https://www.python.org/downloads/>`_.
    Make sure to select *add Python to PATH* option.
  * Cygwin is required to provide the UNIX-standard tools listed above.
    Cygwin may be downloaded from `Cygwin.com <http://cygwin.com/install.html>`_.
    Install Cygwin with all the recommended packages, plus rsync and openssh.
  * ``node`` is available at `Nodejs.org <http://nodejs.org/>`_. This installer
    will also install ``npm``. To ensure that npm is up to date, run
    ``npm update -g npm`` from a command prompt with Administrator permissions
    after the install is complete.
  * ``git`` is available at `git-scm.org <http://git-scm.com/downloads>`_.

You will have to add the Cygwin binaries to the Windows path manually. To do
this on Windows 7, go to the "System" control panel item and click on
"Advanced System Settings" in the left column. Next, go to the
"Advanced" panel and click "Environment Variables". From there, find
"Path" in the "System Variables" list and append a semicolon followed by
your Cygwin binary path, by default ``C:\cygwin64\bin``.

If you don't already have an ssh keypair you wish to use, run the
command ``ssh-keygen`` from the Cygwin64 Terminal. By default, the keys
will be in the Cygwin home folder - you may wish to move them to make
the path to them easier to enter later.

Install Additional Packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once these key tools for your environment are installed, the following
additional packages must be installed from a terminal. On Windows, use
a command prompt in Administrator mode and leave off the "sudo" from
each command.
  * ``bower`` must be installed with ``sudo npm install -g bower``.
  * ``grunt`` and ``grunt-cli`` must be installed with
    ``sudo npm install -g grunt grunt-cli``.
  * ``forever`` must be installed with ``sudo npm install -g forever``.

All of the above packages may be installed in a single command with
``sudo npm install -g bower grunt grunt-cli forever``.

Once the necessary packages are installed, run ``sudo npm install`` and
``bower install`` in that order from the directory you're using for
your source repository.

Set up a Development target
---------------------------

FreeNAS 10 UI development works by pushing all changes immediately to a target
FreeNAS instance. This instance should be dedicated solely to FreeNAS
development and not contain any important data nor support any services
in actual use. Additionally, FreeNAS development target instances cannot
be shared - unpredictable results may occur if two or more developers
attempt to use the same FreeNAS instance as a target.

Requirements for FreeNAS Instance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A FreeNAS instance to be used as a target for FreeNAS development must
be configured as follows:

 *  rsync is enabled (enabled by default in FreeNAS 10 as of March 2015).
 *  ssh is enabled with root login allowed. Password login enabled may also
    help (both are enabled by default in FreeNAS 10 as of March 2015).
 *  Has a public key installed for the FreeNAS root user, with the
    corresponding private key in your development environment.

Initialize Your FreeNAS Instance and Development Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Begin this process only once you have completed setup of your
development environment and your target FreeNAS instance is configured
as described. To begin the FreeNAS initialization process, navigate to
the directory on your development environment where you're keeping the
frontend source. By default this is <repository root>/src/gui/. Once
you're there, run the command ``grunt``. A series of scripts will
execute, first requesting information about how to connect to your FreeNAS
instance and then sanity checking and installing all the necessary
software to your FreeNAS instance. This will also install your local
version of the FreeNAS GUI webapp to your FreeNAS instance.

Once ``grunt`` is running and displaying the IP address of your FreeNAS
development instance, you are ready to develop for the FreeNAS 10
frontend!
