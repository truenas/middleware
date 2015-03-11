// Power Flux Store
// ----------------
// This is suraj's experimental setup might change or go away completely

"use strict";

var _            = require("lodash");
var EventEmitter = require("events").EventEmitter;

var FreeNASDispatcher = require("../dispatcher/FreeNASDispatcher");
var FreeNASConstants  = require("../constants/FreeNASConstants");

var PowerMiddleware = require("../middleware/PowerMiddleware");

var ActionTypes  = FreeNASConstants.ActionTypes;
var CHANGE_EVENT = "change";
var UPDATE_MASK  = ["power.changed", "update.changed"];

var _rebootscheduled    = false;
var _shutdownscheduled  = false;
var _updatehappening    = false;

var PowerStore = _.assign( {}, EventEmitter.prototype, {

    emitChange: function() {
      this.emit( CHANGE_EVENT );
    }

  , addChangeListener: function( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  , getUpdateMask: function() {
      return UPDATE_MASK;
    }

  , isEventPending: function() {
      return ( _rebootscheduled || _shutdownscheduled || _updatehappening );
    }

  , isRebootPending: function() {
      return _rebootscheduled;
    }

  , isShutDownPending: function () {
      return _shutdownscheduled;
  }

  , areWeUpdating: function () {
      return _updatehappening;
  }

});

PowerStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {
  var action = payload.action;

  switch( action.type ) {

    case ActionTypes.MIDDLEWARE_EVENT:
      var args = action.eventData.args;

      if ( UPDATE_MASK.indexOf(args["name"]) !== -1  ) {
        var updateData = args["args"];

        if ( args["name"] === "power.changed" && updateData["operation"] === "reboot" ) {
          _rebootscheduled = true;
          console.log("Suraj reboot event being caught by the Powerstore");
        } else if ( args["name"] === "power.changed" && updateData["operation"] === "shutdown" ) {
          _shutdownscheduled = true;
        } else if ( args["name"] === "update.changed" && updateData["operation"] === "started" ) {
          _updatehappening = true;
        } else {
          // TODO: Can this be anything else?
        }

        PowerStore.emitChange();

      // TODO: Make this more generic, triage it earlier, create ActionTypes for it
      } else if ( args["name"] === "task.updated" && args.args["state"] === "FINISHED" ) {
        // do something (might just remove this!);
        // even if the above args["name"] was not "update.changed" it does not hurt to do the below
        // as the only time when _rebootscheduled will go to false back if it was made true is 
        // AFTER the system came back (with a fresh set of values) kidda same for _shutdownscheduled
        _updatehappening = false;
      }

      break;

    default:
      // No action
  }
});

module.exports = PowerStore;
