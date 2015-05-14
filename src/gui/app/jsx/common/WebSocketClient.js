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

// Timer object (code taken from: http://stackoverflow.com/questions/3144711/javascript-find-the-time-left-in-a-settimeout/20745721#20745721)
// the above code is modified to be able to suit what we need it to do
// This is primarily needed so that the reconnection interval can be
// obtained at the same time while the timer is in use.
// delay is to be specified in milliseconds (example 10000 for 10 seconds)
function ReconnectTimer ( doAfter, delay ) {
  var id, started, running;
  var remaining = 0;
  if ( delay && typeof delay !== "undefined" ) {
    remaining = delay;
  }

  this.start = function ( delay ) {
    // console.log( "suraj in ReconnetTimers start" );
    if ( delay ) {
      remaining = delay;
    }
    running = true;
    started = new Date();
    id = setTimeout( doAfter, remaining );
  };

  this.pause = function ( ) {
    running = false;
    clearTimeout( id );
    remaining -= new Date() - started;
  };

  this.getTimeLeft = function ( ) {
    remaining -= new Date() - started;
    return remaining;
  };

  this.isRunning = function ( ) {
    remaining -= new Date() - started;
    if ( remaining <= 0 ) {
      running = false;
      // console.log( "suraj clearing the timeout" );
      clearTimeout( id );
    }
    return running;
  };

  this.stop = function ( ) {
    clearTimeout( id );
    running = false;
    //doAfter = null;
    remaining = 0;
  };

};

class WebSocketClient {

  constructor () {
    // Counter for stepped timeout
    this._k = 0;
    this.socket = null;

    // Publically accessible reconectHandle
    this.reconnectHandle = new ReconnectTimer ( function ( ) {
      var protocol = ( window.location.protocol === "https:" ? "wss://" : "ws://" );
      this.connect( protocol + document.domain + ":5000/socket" );
    }.bind( this ) );

  }


// This method should only be called when there's no existing connection. If for
// some reason, the existing connection should be ignored and overridden, supply
// `true` as the `force` parameter.
  connect ( url, force ) {
    console.log( url );
    if ( window.WebSocket ) {
      if ( !this.socket || force ) {

        DL.info( "Creating WebSocket instance" );

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

      } else if ( DL.reoports( "connection" ) ) {
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
    this.k = 0;
  }

  handleMessage () {

  }

  handleError () {

  }

  handleClose () {
    if ( !this.reconnectHandle.isRunning() ) {
      this.reconnectHandle.start( MODFIBONACCI[this.k] );
    }
    var _this = this;
    ( function checkReconnectHandle ( ) {
      // console.log( "suraj in checkReconnectHandle... time remaining is: ", _this.reconnectHandle.getTimeLeft() );
      setTimeout( function () {
        if ( _this.reconnectHandle.isRunning() ) {
          checkReconnectHandle();       // Call checkReconnectHandle again
        } else if ( !this.socket ) {
          // Increase k in a cyclic fashion (it goes back to 0 after reachin 4)
          _this.k = ++_this.k % MODFIBONACCI.length;
          _this.reconnectHandle.stop();
          _this.reconnectHandle.start( MODFIBONACCI[_this.k] );
        }
      }, 500 );
    }() );
  }

}

export default WebSocketClient;
