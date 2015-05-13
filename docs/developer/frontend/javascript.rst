============
Introduction
============

FreeNAS 10 Frontend uses a strict style guide and a highly encouraged set of
other best practices for all JavaScript and JSX code. The goal of these rules is
to make contibuting to FreeNAS 10 easier, by reducing the need to grasp and
duplicate multiple code styles in different parts of the codebase. Additionally,
several of the rules are aimed toward increasing readability and making simple
errors immediately obvious.

The tool used for testing for and displaying style guide deviations is JSCS.
For the exact JSCS rules used in FreeNAS 10, look at the ``.jscsrc`` file in the
root of the FreeNAS 10 source code.

The :ref:`Frontend Dev Environment` includes a tool for automatically checking
compliance with all style guide rules. There are also :ref:`JSCS Plugins` for
popular editors that show JavaScript errors, warnings, and style guide
deviations live as you develop.

JavaScript Code Rules
---------------------

Our style rules are based largely on the rules from the
`node style guide <https://github.com/felixge/node-style-guide>`__, with
selected rules added from the
`npm style guide <https://docs.npmjs.com/misc/coding-style>`__. This guide is
largely adapted from those two sources.

JSCS Plugins
------------

There are JSCS for a number of popular editors. This guide will cover only
editors known to be in popular use among FreeNAS 10 developers.

For a list of other plugins and tools, see the
`JSCS website <http://jscs.info/overview.html#friendly-packages>`_.

SublimeText
~~~~~~~~~~~

vim
~~~

This was done on PC-BSD 10.1, the process for installing and configuring
Syntastic may differ on your distribution of choice.

1. ``sudo npm install -g jscs``
2. ``sudo npm install -g esprima-fb``
3. ``cd ~/.vim``
4. ``mkdir bundle``
5. ``mkdir plugin``
6. ``mkdir autoload``
7. ``curl -LSso ~/.vim/autoload/pathogen.vim https://tpo.pe/pathogen.vim``
8. ``cd ~/.vim/bundle``
9. ``git clone https://github.com/scrooloose/syntastic.git``
10. Edit ``~/.vimrc`` and add these lines to the end of it (copy the default 
    one over from ``/usr/local/share/vim/vim74/vimrc_example.vim`` if you 
    don't already have one):

.. code-block:: vim

   call pathogen#infect()

   set statusline+=%#warningmsg#
   set statusline+=%{SyntasticStatuslineFlag()}
   set statusline+=%*

   let g:syntastic_always_populate_loc_list = 1
   let g:syntastic_auto_loc_list = 1
   let g:syntastic_check_on_open = 1
   let g:syntastic_check_on_wq = 0
   autocmd FileType javascript let b:syntastic_checkers = findfile('.jscsrc', '.;') != '' ? ['jscs'] : ['jshint']

.. note::
   This configuration will make JSCS work so long as you open files from
   within a terminal in the FreeNAS build directory. If you want it to work a
   little more universally (i.e. opening files in gVim from a file manager)
   you can create a symbolic link from your home directory to the ``.jscsrc`` 
   in your FreeNAS source directory.

For more information on the Syntastic vim plugin please visit their GitHub page:
`Syntastic GitHub <https://github.com/scrooloose/syntastic>`_

emacs
~~~~~

atom
~~~~

Awaiting a volunteer to document how to install the
`Atom JSCS plugin <https://atom.io/packages/linter-jscs>`_!

------------------

This page licensed under CC-BY-SA.

.. image:: images/cc-by-sa-88x31.png
