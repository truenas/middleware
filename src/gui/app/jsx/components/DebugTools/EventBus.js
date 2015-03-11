// DEBUG TOOLS EVENT BUS
// =====================
// Small event bus to assist with showing and hiding the Debug Tools pane.

"use strict";

var _            = require("lodash");
var EventEmitter = require("events").EventEmitter;

var EventBus = _.assign( {}, EventEmitter.prototype, {

    emitToggle: function() {
      this.emit( "toggle" );
    }

  , addListener: function( callback ) {
      this.on( "toggle", callback );
    }

  , removeListener: function( callback ) {
      this.removeListener( "toggle", callback );
    }

});

module.exports = EventBus;
