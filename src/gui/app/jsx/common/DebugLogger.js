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
    this.defaultType = defaultType || "log";
    this.namespace = namespace || null;
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

  static formatOutput () {
    let output = [];

    if ( _.isArray( contents ) ) {
      output.concat( contents );
    } else {
      output.push( contents );
    }

    if ( _.isArray( css ) && css.length ) {
      output.concat( css.map( style => DEBUGCSS[ style ] ) );
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
          console[ type ]
            .apply( null
                  , this.constructor.formatOutput( contents, css )
                  );
          break;

        default:
          console.log
            .apply( null
                  , this.constructor.formatOutput( contents, css )
                  );
          break;
      }
    }
  }

  // Shortcut methods aliasing write(). Reduces clutter in calls.
  dir () {
    this.write.apply( [ "dir" ].concat( arguments ) )
  }
  error () {
    this.write.apply( [ "error" ].concat( arguments ) )
  }
  info () {
    this.write.apply( [ "info" ].concat( arguments ) )
  }
  log () {
    this.write.apply( [ "log" ].concat( arguments ) )
  }
  table () {
    this.write.apply( [ "table" ].concat( arguments ) )
  }
  trace () {
    this.write.apply( [ "trace" ].concat( arguments ) )
  }
  warn () {
    this.write.apply( [ "warn" ].concat( arguments ) )
  }

  group ( type, flag, heading, contents, css ) {

  }

};

export default DebugLogger;
