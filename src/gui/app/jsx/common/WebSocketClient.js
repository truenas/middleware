// WEBSOCKET CLIENT
// ================
// A simple base class for the WebSocket clients used by FreeNAS 10. Implements
// some shared functionality that all WS clients rely on.

"use strict";

import _ from "lodash";

import DebugLogger from "./DebugLogger";

const DL = new DebugLogger( "MIDDLEWARE_CLIENT_DEBUG" );

// Modified fibonacci series to use with stepped timeout
const MODFIBONACCI = [ 5000, 8000, 13000, 21000, 34000 ];

// Timer object (code taken from: http://stackoverflow.com/questions/3144711/...
// ...javascript-find-the-time-left-in-a-settimeout/20745721#20745721)
// the above code is modified to be able to suit what we need it to do
// This is primarily needed so that the reconnection interval can be
// obtained at the same time while the timer is in use.
// delay is to be specified in milliseconds (example 10000 for 10 seconds)
function ReconnectTimer ( doAfter, delay ) {
  let idTimeout, idInterval, running;
  let remaining = 0;
  let updateFunc = function () {};
  let modAfter = function ( ) {
    running = false;
    remaining = 0;
    doAfter();
  };
  if ( delay && typeof delay !== "undefined" ) {
    remaining = delay;
  }

  let myCusTimeout = function  ( code, delay, listener, interval ) {
    let elapsed = 0;
    let h;
    h = setInterval( function () {
      elapsed += interval;
      if ( elapsed < delay ) {
        listener( delay - elapsed );
      } else {
        clearInterval( h );
      }
    }, interval );
    return [ h, setTimeout( code, delay ) ];
  };

  let modUpdateFunc = function ( t ) {
    remaining = t;
    updateFunc( t );
  };

  this.setUpdateFunc = function ( foo ) {
    updateFunc = foo;
  };

  this.start = function ( delay ) {
    if ( delay ) {
      remaining = delay;
    }
    running = true;
    [ idInterval, idTimeout ] = myCusTimeout( modAfter
                                             , remaining
                                             , modUpdateFunc
                                             , 100 );
  };

  this.pause = function ( ) {
    running = false;
    clearTimeout( idTimeout );
    clearInterval( idInterval );
  };

  this.getTimeLeft = function ( ) {
    if ( running ) {
      return remaining;
    } else {
      remaining = 0;
      return 0;
    }
  };

  this.isRunning = function ( ) {
    if ( remaining === 0 ) { running = false };
    return running;
  };

  this.stop = function ( ) {
    clearTimeout( idTimeout );
    clearInterval( idInterval );
    running = false;
    this.remaining = 0;
  };

  this.reconnectNow = function ( ) {
    this.stop();
    doAfter();
  };
};


class WebSocketClient {

  constructor () {
    // Counter for stepped timeout
    this.k = -1;
    this.socket = null;

    // Publically accessible reconectHandle
    this.reconnectHandle = new ReconnectTimer ( function ( ) {
      var protocol = ( window.location.protocol === "https:" ?
                         "wss://" : "ws://" );
      this.connect( protocol + document.domain + ":5000/socket" );
    }.bind( this ) );
  }


  // This method should only be called when there's no existing connection. If
  // for some reason, the existing connection should be ignored and overridden,
  // supply `true` as the `force` parameter.
  connect ( url, force ) {
    if ( window.WebSocket ) {
      if ( !this.socket || force ) {

        if ( DL.reports( "connection" ) ) {
          DL.info( "Creating WebSocket instance" );
        }

        if ( force ) {
          DL.warn( "Forcing creation of new WebSocket instance" );
        }

        this.socket = new WebSocket( url );

        _.assign( this.socket
                , { onopen: this.handleOpen.bind( this )
                  , onmessage: this.handleMessage.bind( this )
                  , onerror: this.handleError.bind( this )
                  , onclose: this.handleClose.bind( this )
                  }
                , this
                );

      } else if ( DL.reports( "connection" ) ) {
        DL.warn( "Attempted to create a new WebSocket connection while a " +
                 "connection already exists."
               );
      }
    } else {
      // TODO: Visual error for legacy browsers with links to download others
      DL.error( "This browser doesn't support WebSockets." );
    }
  };

  // Shortcut method for closing the WebSocket connection. Will also trigger
  // `handleClose` for any cleanup that needs to happen.
  disconnect ( code, reason ) {
    this.socket.close( code, reason );
  };

  handleOpen () {
    // Set stepped reconnect counter back to 0
    this.k = -1;
  }

  handleMessage () {

  }

  handleError () {

  }

  handleClose () {
    this.socket = null;
    if ( this.reconnectHandle.isRunning() ) {
      this.reconnectHandle.stop();
    }
    // Increase k in a cyclic fashion (it goes back to 0 after reachin 4)
    this.k = ++this.k % MODFIBONACCI.length;
    this.reconnectHandle.start( MODFIBONACCI[this.k] );
    // Uncomment the below if debugging the reconnect timer, else let it be!
    // var _this = this;
    // ( function checkReconnectHandle ( ) {
    //     let tvar = 0;
    //     setTimeout( function () {
    //       if ( _this.reconnectHandle.isRunning() ) {
    //         let temp = Math.round( _this.reconnectHandle.getTimeLeft()/1000);
    //         if ( temp !== tvar ) {
    //           tvar = temp;
    //           console.log( tvar, " seconds to reconnection..." );
    //         };
    //         checkReconnectHandle();       // Call checkReconnectHandle again
    //       }
    //     }, 1000 );
    //   }() );
  }

}

export default WebSocketClient;
