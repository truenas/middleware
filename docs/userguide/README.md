To build the User Guide from source:

Install the following (these are the FreeBSD package names):

- devel/git
- textproc/py-sphinx
- textproc/py-sphinx_numfig
- textproc/py-sphinxcontrib-httpdomain

Next, determine where you want to store the source code and change to that directory (we'll refer to it as /path/to/your-build-directory). Then, check out the
source code from git as your regular user account:

```
% cd /path/to/your-build-directory
% git clone git://github.com/freenas/freenas.git
% cd freenas
% git checkout 9.3-STABLE

```

NOTE: all of the following commands should be run from /path/to/your-build-directory/freenas/.

To set up the doc build environment for the first time:

```
% sphinx-quickstart 
```

To build a local copy of the HTML, run this command in /path/to/your-build-directory/freenas/docs/userguide:

```
sphinx-build -b html . _build
```
When finished, open _build/freenas.html in a browser to verify the HTML output.

To build a local copy of the HTML as one long page, with the entire table of contents in the left frame, use this command instead:

```
sphinx-build -b singlehtml . _build
```

To build a PDF version of the userguide you will need a few extra packages:

- print/tex-formats (this will pull in a LOT of dependencies)
- print/tex-dvipsk
- devel/gmake

Run this command TWICE to build the PDF:
```
yes '' | gmake latexpdf
```
When finished running the second time, you will find the PDF in _build/latex/FreeNAS.pdf.

To build a local EPUB, run this command:

```
sphinx-build -b epub . _build
``
