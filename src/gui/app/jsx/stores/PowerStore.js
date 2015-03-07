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
var UPDATE_MASK  = "power.changed";

var _updatedOnServer    = [];
var _localUpdatePending = {};

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

  , isPowerUpdatePending: function( id ) {
      return _updatedOnServer.indexOf( id ) > -1;
    }

});

PowerStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {
  var action = payload.action;

  switch( action.type ) {

    case ActionTypes.MIDDLEWARE_EVENT:
      var args = action.eventData.args;

      if ( args["name"] === UPDATE_MASK ) {
        var updateData = args["args"];

        if ( updateData["operation"] === "reboot" ) {
          // FIXME: This is a workaround for the current implementation of task
          // subscriptions and submission resolutions.
        } else if ( updateData["operation"] === "shutdown" ) {
          // do something else
        } else {
          // TODO: Can this be anything else?
        }

        PowerStore.emitChange();

      // TODO: Make this more generic, triage it earlier, create ActionTypes for it
      } else if ( args["name"] === "task.updated" && args.args["state"] === "FINISHED" ) {
        delete _localUpdatePending[ args.args["id"] ];
      }

      break;

    default:
      // No action
  }
});

module.exports = PowerStore;
