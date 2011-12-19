:Author: Garrett Cooper
:Date: $Date$
:Revision: $Rev$
:Copyright: BSD Licensed to FreeNAS project (c/o iXsystems, Inc.)

.. contents:: :depth: 2

============
Introduction
============

All of the documents in the FreeNAS project should be written in RST for the
following reasons:

#. FreeNAS 8.x is written primarily in python, and RST is a python standard
   method of formulating documentation.
#. RST is easy to digest in plaintext format, and thus also easier to review
   with simple reviewing tools like ReviewBoard.
#. You don't need an external service to host the documentation (e.g. Google
   Docs), and some webservers support automatic RST -> HTML conversion.
#. RST can be converted to a number of other potentially easier to digest
   formats (such as HTML, Manpages, LaTeX, OpenOffice, PDF, etc).
#. The docs are live with the sourcecode, thus the docs are most likely more
   relevant to whatever is done in the source tree (assuming the authors are
   keeping things up-to-date).

============
Installation
============

Installing docutils is fairly simple and painless. The following documentation
assumes that you're running FreeBSD, but you should be able to invoke whatever
distro specific commands you want to install docutils as well.

NOTE: the following instructions assume you're running as root.

--------------------
From Binary Packages
--------------------

In short, it depends on what version of ports the package(s) were originally
built against, because depending on the version, the package you need to
install might differ.

Odds are more than likely the following will work for you::

   # pkg_add -r py26-docutils

If you have a newer OS than say, 8.x, try substituting py26 with py27, etc.

--------------------
From Source
--------------------

Here's how you would build the docutils port::

   # cd /usr/ports
   # cd textproc/py-docutils
   # make install

===========
Some Basics
===========

The following section(s) quickly go over some examples of how to do RST.

---------------------------------------
Quotes, Italics, and Boldface -- oh my!
---------------------------------------

Quotes use double backticks (``````); italics use single asterisks (``*``);
and boldface uses double asterisks (``**``). Example::

    Tony Montana said: ``I always tell the truth. Even when I lie.``

    Tony Montana: I always tell the truth. *Even* when I lie.

    Tony Montana: You wanna play rough? Okay. **Say hello to my little friend**!

And now the rendered version:

Tony Montana said: ``I always tell the truth. Even when I lie.``

Tony Montana: I always tell the truth. *Even* when I lie.

Tony Montana: You wanna play rough? Okay. **Say hello to my little friend**!

--------------
Bulleted Lists
--------------

Bullets can be simply done by preceding a list of items with a ``-``, ``*``,
or ``+``. Example::

    - Foo
        + Bar
            * Baz
        + Barge
    - Zanzibar

And now the rendered version:

- Foo
    + Bar
        * Baz
    + Barge
- Zanzibar

--------------
Numbered Lists
--------------

Numbered lists can be simply done by preceding a list of items with a ``#.``,
or the equivalent number, e.g. ``1.``, etc; the author highly recommends the
``#.`` format though because it automatically enumerates the list
appropriately -- you'll just need to set the style appropriate to the sublist,
e.g. ``a.``, ``i.``, etc. There are other variants of the numbering format
(e.g. ``#)``, etc), as noted in the various RST guides linked from
`Other References`_, but for simplicity and consistency, the author prefers
the ``#.`` format. Example::

    #. Foo
        a. Bar
            i. Baz
            #. Haze
        #. Barge
    #. Zanzibar

And now the rendered version:

#. Foo
    a. Bar
        i. Baz
        #. Haze
    #. Barge
#. Zanzibar

----------
Sections
----------

Sections are like <h1>, <h2>, <h3>, etc in HTML (or the Header* styles in MS
Office). They provide a means to cordon off portions of a document in a
logical manner; plus, if you define a table of contents rst2html will produce
one on demand for you based on the settings used when defining the ToC --
similar to MS Word!

Example::

    +++++++++
    Section 1
    +++++++++

    @@@@@@@@@@
    Section 1a
    @@@@@@@@@@

    +++++++++
    Section 2
    +++++++++

The key takeaway from doing this is that you need to be structured in terms of
how you formulate your headers, i.e.

    #. You need to use characters as sections that are consistent with that
       given level, e.g. in the above example ``++++`` denotes the first
       section level, whereas ``@@@@`` denotes the second section level.
    #. The characters must be as long as the section title, or longer. It's up
       to you which kind you wish to use.

And now here's the interpreted text:

+++++++++
Section 1
+++++++++

@@@@@@@@@@
Section 1a
@@@@@@@@@@

+++++++++
Section 2
+++++++++

-----------
Code Blocks
-----------

Code blocks -- or what RST calls ``literal blocks``, or what some in the HTML
community refer to with <pre>..</pre> blocks -- are blocks of text that are
interpreted literally, instead of being interpreted by the RST interpreter.

Example::

    A first year CS student might be proud of the following program after
    the first day of class::

        #!/usr/bin/env python
        """My 'first' python program :D!

        :Author: Jane Doe
        :Date: $Date$:
        """

        print "Hello world!"

Normally this would be interpreted like the following, but since the above text
is in a literal block, the RST interpreter interprets them as literal text.

A first year CS student might be proud of the following program after
their first day of class::

    #!/usr/bin/env python
    """My 'first' python program :D!

    :Author: Jane Doe
    :Date: $Date$:
    """

    print "Hello world!"

----------
Hyperlinks
----------

There are a number of ways to do hyperlinks. The most common forms are:

  - Internal References
  - External References

Internal references can be thought of as relative hyperlinks, e.g.
docs/using-rst.rst as opposed to
http://freenas.svn.sourceforge.net/viewvc/freenas/trunk/docs/using-rst.rst .

External references are similar to externally pointing hyperlinks, e.g.
http://freenas.svn.sourceforge.net/viewvc/freenas/trunk/docs/using-rst.rst ,
as opposed to docs/using-rst.rst .

Example::

    Here's an external reference to `FreeNAS <http://www.freenas.org>`_.

    Here's another external reference using an External Hyperlink target to the
    FreeNAS SourceForge Project_ page.

    Here's an external reference to SourceForge, all spelled out:
    http://www.sourceforge.net

    Here's an ``internal`` link back to `this <using-rst.rst>`_ document.

    .. _Project: http://www.sourceforge.net/projects/freenas

And now, the rendered version:

Here's an external reference to `FreeNAS <http://www.freenas.org>`_.

Here's another external reference using an External Hyperlink target to the
FreeNAS SourceForge Project_ page.

Here's an external reference to SourceForge, all spelled out:
http://www.sourceforge.net

Here's an ``internal`` link back to `this <using-rst.rst>`_ document.

.. _Project: http://www.sourceforge.net/projects/freenas

==========
What Next?
==========

Congratulations! Now you should have the basic tools that you need to install
and write basic RST documentation. Feel free to run::

   rst2html using-rst.rst

to see the HTML version of this file (if you aren't viewing it already)!

Make sure to check out the `Other References`_ section for more in-depth
documentation on that describe how to write RST docs.

================
Other References
================

  #. docutils project recommended user documentation: http://docutils.sourceforge.net/rst.html#user-documentation
  #. The RST Quickstart Guide: http://docutils.sourceforge.net/docs/user/rst/quickstart.html (highly recommend)
  #. Full docutils documentation reference: http://docutils.sourceforge.net/rst.html#reference-documentation

