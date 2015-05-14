// MIDDLEWARE CLIENT DEBUG
// =======================
// Companion class for Middleware Client. Abstracts out some of the more
// cumbersome debug methods to keep process flow simple and obvious in the
// Middleware Client.

"use strict";

import DebugLogger from "../common/DebugLogger";

class MiddlewareClientDebug extends DebugLogger {

  constructor () {
    super();
  }

  static logPack ( namespace, name, args, id ) {
    let validPack = true;
    let prefix = "BAD PACK: ";

    if ( !_.isString( namespace ) ) {
      validPack = false;
      this.constructor.warn( "packing"
                           , prefix + "Provided namespace was not a string for request " +
                             "%c'${ id }'%c"
                           , [ DEBUGCSS.idColor, DEBUGCSS.defaultStyle ]
      );
    }
    if ( !_.isString( name ) ) {
      validPack = false;
      this.constructor.warn( "packing"
             , prefix +
               "Provided name was not a string for request %c'${ id }'%c"
             , [ DEBUGCSS.idColor, DEBUGCSS.defaultStyle ]
             );
    }
    if ( typeof args === ( "null" || "undefined" ) ) {
      validPack = false;
      this.constructor.warn( "packing"
             , prefix +
               "Provided args value was null or undefined for request " +
               "%c'${ id }'%c"
             , [ DEBUGCSS.idColor, DEBUGCSS.defaultStyle ]
             );
    }
    if ( !_.isString( id ) ) {
      validPack = false;
      let packArgs = args
                   ? ":" + args
                   : "";

      this.constructor.warn( "packing"
             , prefix +
               "UUID %c'${ id }'%c for '${ namespace }'${ packArgs } had " +
               "to be generated because none was provided%c"
             , [ DEBUGCSS.idColor, DEBUGCSS.defaultStyle ]
             );

    }

    if ( validPack ) {
      this.constructor.info( "Packed request %c'${ id }'%c successfully."
             , [ DEBUGCSS.idColor, DEBUGCSS.defaultStyle ]
             );
    } else {
      this.constructor.log(
        [ "Dump of bad pack:"
        , { namespace: namespace
          , name: name
          , id: id
          , args: args
          }
        ]
      );
    }
  }

  static logPythonTraceback ( requestID, args, originalRequest ) {
    console.groupCollapsed( "%cRequest %c'" + requestID + "'%c caused a Python traceback", DEBUGCSS.errorColor, DEBUGCSS.idColor, DEBUGCSS.errorColor );
    if ( originalRequest ) {
      console.groupCollapsed( "Original request" );
      console.log( originalRequest );
      console.groupEnd();
    }
    console.groupCollapsed( "Response data" );
    console.log( args );
    console.groupEnd();
    console.log( "%c" + args.message , DEBUGCSS.codeStyle );
    console.groupEnd();
  }

  static logErrorWithCode ( requestID, args, originalRequest ) {
    console.groupCollapsed( "%cERROR %s: Request %c'%s'%c returned: %s", DEBUGCSS.errorColor, args.code, DEBUGCSS.idColor, requestID, DEBUGCSS.errorColor, args.message );
    if ( originalRequest ) {
      console.groupCollapsed( "Original request" );
      console.log( originalRequest );
      console.groupEnd();
    }
    console.log( args );
    console.groupEnd();
  }

  static logErrorResponse ( requestID, args, originalRequest ) {
    console.groupCollapsed( "%cERROR: Request %c'" + requestID + "'%c returned with an error status", DEBUGCSS.errorColor, DEBUGCSS.idColor, DEBUGCSS.errorColor );
    if ( originalRequest ) {
      console.groupCollapsed( "Original request" );
      console.log( originalRequest );
      console.groupEnd();
    }
    console.log( args );
    console.groupEnd();
  }

}

export default new MiddlewareClientDebug( "MIDDLEWARE_CLIENT_DEBUG" );