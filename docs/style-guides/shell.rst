:Author: Garrett Cooper
:Date: $Date: 2012-01-13 09:18:22 -0800 (Fri, 13 Jan 2012) $
:Revision: $Rev: 9519 $
:Copyright: Shell Style Guide

.. contents:: :depth: 2

============
Introduction
============

The following guide will go over the shell coding standard for the
FreeNAS project.

==========
In General
==========

Style must be consistent with the surrounding code, in particular if
it's contributed via a third party. This requirement has been
established to be consistent with style(9)'s requirements in FreeBSD --
despite the fact that style(9) applies solely to C code.

=====================
Variable Declarations
=====================

* Variable names should be complete and descript. The reader should be
  able to discern what the intent of the variable is from the name.
* Variables should be defined and declared separately, e.g.::

    local foo="$1"

  is discouraged, when compared with::

    local foo

    foo="$1"

* If your variable is multiword, it must be quoted in order to avoid
  word splitting in /bin/sh under FreeBSD.

==========
Whitespace
==========

* Use 72 columns as a soft limit and 79 columns as a hard limit.
* Use hard-tabs, instead of 4-space indentation. This is done to
  conform to the FreeBSD project shell coding style.

=================
set -e and set -u
=================

Using set -e and set -u will help the developer find potential bugs in
his/her code related to bad exit codes and unset variables. If set -e
is used in tandem with set -u, sh will stop whenever a variable is
unset.

======================
Conditionals and Loops
======================

Conditionals should be composed in this format::

    if :
    then
        # This will always be executed
    fi

    while : ; do
        # Do something here
        :
    done

===============
Local variables
===============

If the scope of a variable (even a loop variable) is local to the
function, one should always be declared local.

==================
Readonly variables
==================

Constants in scripts should be sprinkled with readonly attributes to
   #. Become self-documenting.
   #. Make set -e more meaningful as set -e with readonly variables
      will cause a script to error out.

===================
Miscellaneous Items
===================

Hereto-docs
===========

hereto-docs are constructs that allow the author to compose multiline
inputs to various commands (e.g. cat). An example follows::

    cat > a-file <<EOF
    this is a multiline
    message
    EOF

The FreeBSD project as well as many other projects compose hereto
docs in the above format. Furthermore, using the above format improves
readability in emacs, vim, etc, in particular when things are
colorized.

   
