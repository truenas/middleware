FreeNAS documentation is stored as ASCII text files, that end in a .rst extension, within the FreeNAS source repository. The FreeNAS Project uses the
Sphinx Python documentation generator to generate documentation in HTML format. Anyone can download the documentation source and generate their own copy of
the documentation in HTML or PDF formats. Users with a github account can also edit the documentation and generate git pull requests so that the edits can be
reviewed and committed. This README contains instructions for getting the source, generating a copy of the documentation, and issuing a git pull request. It
assumes that the reader is using these instructions on either a FreeBSD/PC-BSD system or a FreeBSD jail.

##Requirements:

To build (and/or make changes to) the upcoming version of the User Guide:

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

##Building the Documentation

NOTE: all of the following commands should be run from /path/to/your-build-directory/freenas/.

To set up the doc build environment for the first time:

...

% sphinx-quickstart 

...

If you want to edit the User Guide, make changes to the *.rst file for the chapter to edit, using any ASCII text editor.
The *.rst files are located in /path/to/your-build-directory/freenas/docs/userguide/.
Refer to http://docutils.sourceforge.net/docs/user/rst/quickref.html for formatting syntax.
Refer to http://wiki.typo3.org/Editors_%28reST%29 for a list of reST editors.
Need help getting started or want to discuss edits? Join the http://lists.freenas.org/mailman/listinfo/freenas-docs mailing list.

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
```

##Editing the Documentation

If you want to edit the User Guide, make changes to the *.rst file for the chapter to edit, using any ASCII text editor.
Refer to http://docutils.sourceforge.net/docs/user/rst/quickref.html for help with formatting syntax.
Refer to http://wiki.typo3.org/Editors_%28reST%29 for a list of reST editors.

Need help getting started or want to discuss edits? Join the http://lists.freenas.org/mailman/listinfo/freenas-docs mailing list.

To issue a git pull request containing your edits, use the instructions at https://help.github.com/articles/using-pull-requests.
