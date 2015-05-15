// DEBUG LOGGER
// ============
// A helper class with simple methods for logging debug output to the console.

"use strict";

import _ from "lodash";

const DEBUGCSS =
  { uuid: "color: rgb(33, 114, 218);"
  , args: "color: rgb(215, 110, 20); font-style: italic;"
  , error: "color: rgb(235, 15, 15);"
  , code: "color: rgb(62, 28, 86);"
  , normal: ""
  };

class DebugLogger {

  constructor ( namespace, defaultType ) {
    this.namespace = namespace || null;
    this.defaultType = defaultType || "log";
    this.DEBUGCSS = DEBUGCSS;
  }

  reports ( flag ) {
    if ( typeof window && window.DEBUG_FLAGS ) {
      if ( this.namespace && window.DEBUG_FLAGS[ this.namespace ] ) {
        return Boolean( window.DEBUG_FLAGS[ this.namespace ][ flag ] );
      } else {
        return Boolean( window.DEBUG_FLAGS[ flag ] );
      }
    }

    return false;
  }

  formatOutput ( contents, css ) {
    let output = [];

    if ( contents && contents.length ) {
      if ( _.isArray( contents ) ) {

        output = output.concat( contents );

      } else if ( _.isString( contents ) ) {

        output.push( contents );

      }
    }

    if ( css && css.length ) {
      if ( _.isArray( css ) && css.length ) {

        output = output.concat( css.map( style => this.DEBUGCSS[ style ] ) );

      } else if ( _.isString( css ) && this.DEBUGCSS[ css ] ) {

        output.push( this.DEBUGCSS[ css ] )

      }
    }

    return output;
  }

  write ( type, contents, css ) {
    if ( contents ) {
      switch ( type ) {
        case "dir":
        case "error":
        case "info":
        case "log":
        case "table":
        case "trace":
        case "warn":
          console[ type ]( ...this.formatOutput( contents, css ) );
          break;

        default:
          console.log( ...this.formatOutput( contents, css ) );
          break;
      }
    }
  }

  // Shortcut methods aliasing write(). Reduces clutter in calls.
  dir () {
    this.write( "dir", ...arguments )
  }
  error () {
    this.write( "error", ...arguments )
  }
  info () {
    this.write( "info", ...arguments )
  }
  log () {
    this.write( "log", ...arguments )
  }
  table () {
    this.write( "table", ...arguments )
  }
  trace () {
    this.write( "trace", ...arguments )
  }
  warn () {
    this.write( "warn", ...arguments )
  }

  group ( type, flag, heading, contents, css ) {

  }

};

export default DebugLogger;
