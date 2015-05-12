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
compliance with all style guide rules. There are also :ref:`JSCS Plugins` for popular
editors that show JavaScript errors, warnings, and style guide deviations live
as you develop.

Our style rules are based largely on the rules from the
`node style guide <https://github.com/felixge/node-style-guide>`__, with
selected rules added from the
`npm style guide <https://docs.npmjs.com/misc/coding-style>`__. This guide is
largely adapted from those two sources.

------------------

This page licensed under CC-BY-SA.

.. image:: http://i.creativecommons.org/l/by-sa/3.0/88x31.png
