FreeNAS documentation is stored as ASCII text files, that end in a .rst extension, within the FreeNAS source repository. The FreeNAS Project uses the
Sphinx Python documentation generator to generate documentation in HTML format. Anyone can download the documentation source and generate their own copy of
the documentation in HTML or PDF formats. Users with a github account can also edit the documentation and generate git pull requests so that the edits can be
reviewed and committed. This README contains instructions for getting the source, generating a copy of the documentation, and issuing a git pull request. It
assumes that the reader is using these instructions on either a FreeBSD/PC-BSD system or a FreeBSD jail.

##Requirements:

At a minimum, the following software needs to be installed as the root/superuser. If this is the first time you have used pkg on the system, it may prompt
you to fetch and install it. Say yes to the prompts to do so. Once it is finished, you can then finish installing the needed software.

Instructions are given for both the port and the package as some software may not have a package. Try the pkg command first as it is faster. If the pkg
command succeeds, you do not need to run the make command as the software is already installed; however if it fails, use the make command to install the
software. If the software is already installed, the pkg command will indicate that the most recent version is already installed.

```
portsnap fetch extract
pkg install devel/git (cd /usr/ports/devel/git/ && make install)
pkg install textproc/py-sphinx (cd /usr/ports/textproc/py-sphinx/ && make install)
pkg install textproc/py-sphinxcontrib-httpdomain (cd /usr/ports/textproc/py-sphinxcontrib-httpdomain && make install)
rehash
```

If you wish to generate a PDF version of the documentation, this software also needs to be installed:

```
pkg install print/tex-formats (cd /usr/ports/print/tex-formats/ && make install)
pkg install print/tex-dvipsk (cd /usr/ports/print/tex-dvipsk/ && make install)
pkg install devel/gmake (/usr/ports/devel/gmake/ && make install)
```

Next, determine where you want to store the source code and change to that directory (we'll refer to it as /path/to/your-build-directory). Then, check out the
source code from git:

```
cd /path/to/your-build-directory
git clone -b 9.3-STABLE git://github.com/freenas/freenas.git
cd freenas/docs/userguide
```

##Building the Documentation

All of the following commands need to be run from /path/to/your-build-directory/freenas/docs/userguide. Three formats are currently available: HTML, single
HTML, and PDF. The output of either HTML can be found in /path/to/your-build-directory/freenas/docs/userguide/_build/ and can be viewed in a web browser. The
PDF output will be found in /path/to/your-build-directory/freenas/docs/userguide/_build/latex/FreeNAS.pdf.

To build a local copy of the HTML, with a separate page for each chapter and that chapter's table of contents in the left frame with navigational links
to browse between chapters, run the following command. This is the same format that is published at doc.freenas.org/9.3.

```
sphinx-build -b html . _build
```

To build a local copy of the HTML as one long page, with the entire table of contents in the left frame, use this command instead:

```
sphinx-build -b singlehtml . _build
```

To build a local PDF, run this command TWICE and ignore its error messages:

```
yes '' | gmake latexpdf
yes '' | gmake latexpdf
```

##Editing the Documentation

If you want to edit the User Guide, make changes to the *.rst file for the chapter to edit, using any ASCII text editor.
Refer to http://docutils.sourceforge.net/docs/user/rst/quickref.html for help with formatting syntax.
Refer to http://wiki.typo3.org/Editors_%28reST%29 for a list of reST editors.

Need help getting started or want to discuss edits? Join the http://lists.freenas.org/mailman/listinfo/freenas-docs mailing list.

To issue a git pull request containing your edits, use the instructions at https://help.github.com/articles/using-pull-requests.