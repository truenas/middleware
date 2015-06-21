// MIDDLEWARE CLIENT DEBUG
// =======================
// Companion class for Middleware Client. Abstracts out some of the more
// cumbersome debug methods to keep process flow simple and obvious in the
// Middleware Client.

"use strict";

import _ from "lodash";

import DebugLogger from "../common/DebugLogger";

class MiddlewareClientDebug extends DebugLogger {

  constructor () {
    super( "MIDDLEWARE_CLIENT_DEBUG" );
  }

  logPack ( namespace, name, args, id ) {
    let validPack = true;
    let prefix = "BAD PACK: ";

    if ( !_.isString( namespace ) ) {
      validPack = false;
      this.warn( "packing"
                           , prefix + `Provided namespace was not a string for request ` +
                             `%c'${ id }'%c`
                           , [ this.DEBUGCSS.uuid, this.DEBUGCSS.normal ]
      );
    }
    if ( !_.isString( name ) ) {
      validPack = false;
      this.warn( "packing"
             , prefix +
               `Provided name was not a string for request %c'${ id }'%c`
             , [ this.DEBUGCSS.uuid, this.DEBUGCSS.normal ]
             );
    }
    if ( typeof args === ( "null" || "undefined" ) ) {
      validPack = false;
      this.warn( "packing"
             , prefix +
               `Provided args value was null or undefined for request ` +
               `%c'${ id }'%c`
             , [ this.DEBUGCSS.uuid, this.DEBUGCSS.normal ]
             );
    }
    if ( !_.isString( id ) ) {
      validPack = false;
      let packArgs = args
                   ? ":" + args
                   : "";

      this.warn( "packing"
             , prefix +
               `UUID %c'${ id }'%c for '${ namespace }'${ packArgs } had ` +
               `to be generated because none was provided%c`
             , [ this.DEBUGCSS.uuid, this.DEBUGCSS.normal ]
             );

    }

    if ( validPack ) {
      this.info( `Packed request %c'${ id }'%c successfully.`
             , [ this.DEBUGCSS.uuid, this.DEBUGCSS.normal ]
             );
    } else {
      this.log(
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

  logNewSubscriptionMasks ( masks ) {
    let logMasks = masks.length > 1
                 ? _.clone( masks )
                     .splice( masks.length - 1, 0, " and " )
                     .join( ", " )
                 : masks;

    this.log( `Requested: Subscribe to %c'${ logMasks }'%c events`
            , [ "args", "normal" ]
            );
  }

  logSubscription ( subCount, mask ) {
    if ( subCount > 0 ) {
      this.info( `${ subCount } React components are currently ` +
                 `subscribed to %c'${ mask }'%c events`
               , [ "args", "normal" ]
               );
      this.log( `Increasing subscription count for %c'${ mask }'`, "args" );
    } else {
      this.info( `No React components are currently subscribed to ` +
                 `%c'${ mask }'%c events`
               , [ "args", "normal" ]
               );
      this.log( `Sending subscription request, and setting subscription ` +
                `count for %c'${ mask }'%c to 1`
              , [ "args", "normal" ]
              );
    }
  }

  logUnsubscribeMasks ( masks ) {
    let logMasks = masks.length > 1
                 ? _.clone( masks )
                     .splice( masks.length - 1, 0, " and " )
                     .join( ", " )
                 : masks;

    this.log( `Requested: Subscribe to %c'${ logMasks }'%c events`
            , [ "args", "normal" ]
            );
  }

  logUnsubscribe ( subCount, mask ) {
    if ( subCount === 1 ) {
      this.info( `Only one React component is currently subscribed to ` +
                 `%c'${ mask }'%c events, so the subscription will be removed`
               , [ "args", "normal" ]
               );
      this.log( `Sending unsubscribe request, and deleting subscription ` +
                `count entry for %c'${ mask }'`
              , "args"
              );
    } else {
      this.info( `${ subCount } React components are currently subscribed ` +
                 `to %c'${ mask }'%c events, and one will be unsubscribed`
               , [ "args", "normal" ]
               );
      this.log( `Decreasing subscription count for %c'${ mask }'`, "args" );
    }
  }

  logPythonTraceback ( requestID, args, originalRequest ) {
    console.groupCollapsed( `%cRequest %c'${ requestID }'%c caused a Python traceback`, this.DEBUGCSS.error, this.DEBUGCSS.uuid, this.DEBUGCSS.error );
    if ( originalRequest ) {
      console.groupCollapsed( "Original request" );
      console.log( originalRequest );
      console.groupEnd();
    }
    console.groupCollapsed( "Response data" );
    console.log( args );
    console.groupEnd();
    console.log( "%c" + args.message , this.DEBUGCSS.code );
    console.groupEnd();
  }

  logErrorWithCode ( requestID, args, originalRequest ) {
    console.groupCollapsed( "%cERROR %s: Request %c'%s'%c returned: %s", this.DEBUGCSS.error, args.code, this.DEBUGCSS.uuid, requestID, this.DEBUGCSS.error, args.message );
    if ( originalRequest ) {
      console.groupCollapsed( "Original request" );
      console.log( originalRequest );
      console.groupEnd();
    }
    console.log( args );
    console.groupEnd();
  }

  logErrorResponse ( requestID, args, originalRequest ) {
    console.groupCollapsed( `%cERROR: Request %c'${ requestID }'%c returned with an error status`, this.DEBUGCSS.error, this.DEBUGCSS.uuid, this.DEBUGCSS.error );
    if ( originalRequest ) {
      console.groupCollapsed( "Original request" );
      console.log( originalRequest );
      console.groupEnd();
    }
    console.log( args );
    console.groupEnd();
  }

}

export default new MiddlewareClientDebug();
