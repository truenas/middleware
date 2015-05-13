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

General Rules
~~~~~~~~~~~~~

These are the main rules with which you will interact.


80-column lines
^^^^^^^^^^^^^^^

This is typically for consideration to those using terminal editors with limited
space. However, the real reason we're requiring this is to force you to keep
your code relatively concise. If you find yourself in need of 120 characters
to express a single statement, consider rewriting it. A number of other rules
in this guide will help with keeping your lines short.


Opening Braces on the same Line
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When you use a keyword that requires a bracket to contain the subsequent
statement, put the opening brace of that statement on the same line as the
keyword.

.. code-block:: javascript

   if ( "Good Times" ) { // Good
     console.log( "That's the way uh huh uh huh we like it." );
   } else if ( "pls no" ) // Bad
   {
     console.log( "KNF has its place, but it is not here." );
   }


Method Chaining
^^^^^^^^^^^^^^^

If you must chain method after method, put one on each line, leading with the
dot. This is your way around the 80-character limit when you really need that
long statement.

.. code-block:: javascript

   User
     .findOne({ name: 'foo' })
     .populate( "bar" )
     .exec( function( err, user ) {
       return true;
   });


One Variable per Statement
^^^^^^^^^^^^^^^^^^^^^^^^^^

Declaring a bunch of variables on one line may be appealing, but it makes
finding where a variable is declared annoying and can easily lead to simple
mistakes (like missing commas). Type ``var`` once per variable.

.. code-block:: javascript

   // Good:
   var foo;
   var bar;
   var baz;

   //Bad:
   var
     foo
     , bar
     , baz;

   // Very Bad:
   var foo, bar. baz; //oops!


Use ===
^^^^^^^

Fuzzy comparisons result in fuzzy bugs. Use ===, or lodash ``isEqual``, rather
than ==. != is right out.


Comma First in Multi-Line Lists
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is a bit different. Basically, when you're listing a bunch of things on
multiple lines, each line should start with a comma except the first one. This
lets you line up all the commas under the opening brace or bracket, as a bonus.

The chief benefit of this is that it's immediately obvious when you've forgotten
to put a comma between two items. It also makes those long arrays and objects
much easier to read.

.. code-block:: javascript

   // Good:
   var bestArray = [ foo
                   , bar
                   , baz ];

   // Bad:
   var badArray = [ foo,
                    bar,
                    baz ];

   // Very Bad:
   var uncoolObject { foo: "Don't", bar: "do". baz: "this" }; // Broke it again!


Whitespace
~~~~~~~~~~

There are a number of rules just about where whitespace is forbidden and
required, and how it must be used in general.


Two Space Indentation
^^^^^^^^^^^^^^^^^^^^^

All frontend code must use two-space indentation. Not two-space tabs - two
spaces. On the bright side, that will give you some extra space to work with
compared to 4-space or 8-space tabs, because we also use 80-column lines.


No Trailing Whitespace
^^^^^^^^^^^^^^^^^^^^^^

Whitespace at the end of a line has no reason to exist. This also means that
when a line is just a newline, there shouldn't be any spaces or tabs in it.


Spaces Before Parentheses
^^^^^^^^^^^^^^^^^^^^^^^^^

For just about any keyword that is followed by a parenthesized statement, put
a single space before the opening parenthesis. Function calls are just about the
only time not to use a space before a parenthesis.

.. code-block:: javascript

   var youDoTheGoodThing = true;
   var youDoTheBadThing = { please: "don't" };

   if ( youDoTheGoodThing ) {
     console.log( "Everyone will be happy!" );
   } else if( youDoTheBadThing ){
     console.log( "Everyone, especially you, will be sad when your code is "
                + "full of warnings." );
   }


Spaces Inside Braces and Brackets
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Don't press your braces, brackets, and parentheses up against their contents.
The only exception is when it's an array or object and the very next character
is another brace or bracket. This is mostly for readability.

.. code-block:: javascript

   // Good:
   var floor = { room: "for activities" };

   var hardwareStore = [ "look"
                       , "at"
                       , "all"
                       , "this"
                       , "stuff" ];

   var iStealPets = [{ I: "have"
                     , so: "many" }
                    , { friends: null }];

   // Bad:
   var magicLamp = {phenomenal: "cosmic power"
                   , itty: "bitty living space"}; // eww, it doesn't line up

   var musicalChairs = ["the"
                       , "music"
                       , "stops"];


Spaces Inside Parentheses
^^^^^^^^^^^^^^^^^^^^^^^^^

Whenever you have parentheses around something, put spaces between each
parenthesis and what it contains. The only exception is when it contains an
object.

.. code-block:: javascript

   var youWantToDoItRight = true;
   var youDontWantToDoItRight = "WHY?";

   if ( youWantToDoItRight ) {
     console.log( "You'll do it like this:"
                , { haha: I'm printing an object" });
     console.log( [ "check"
                  , "out"
                  , "this"
                  , "array" ] );
   } else if (youDontWantToDoItRight) {
     console.log("Oh Man I Am Not Good With Computer"
                , [ "pls"
                  , "to"
                  , "help" ]);
   }


.. index:: JSCS Plugins
.. _JSCS Plugins:

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
