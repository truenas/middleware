// ABSTRACT MIDDLEWARE BASE CLASS
// ==============================
// A common abstract base class for all other Middleware classes to extend.
// Among other things, this prevents the class from being constructed with
// `new`, and only allows calling of its static methods. If you need to
// instantiate a Middleware Utility Class, you're probably doing something
// wrong.

"use strict";

class MiddlewareAbstract {
  constructor () {
    throw Error( "Middleware Utility Classes should not be constructed by "
               + "`new`. Call the static methods of this class instead." )
  }
}

export default MiddlewareAbstract;
