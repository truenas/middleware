// Power Flux Store
// ----------------
// This is suraj's experimental setup might change or go away completely

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

var CHANGE_EVENT = "change";
var UPDATE_MASK  = [ "power.changed", "update.changed" ];

var ongoingEvents = {};


var PowerStore = _.assign( {}, EventEmitter.prototype, {

    emitChange: function () {
      this.emit( CHANGE_EVENT );
    }

  , addChangeListener: function ( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function ( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  , getUpdateMask: function () {
      return UPDATE_MASK;
    }

  , isEventPending: function () {
    if ( typeof ( _.keys( ongoingEvents )[0] ) !== "undefined" ) {
      return [ true, ongoingEvents[_.keys( ongoingEvents )[0]]];
    }
    return [ false, "" ];
  }

  , isRebootPending: function () {
    if ( _.values( ongoingEvents ).indexOf( "reboot" ) !== -1 ) {
      return true;
    }
    return false;
  }

  , isShutDownPending: function () {
    if ( _.values( ongoingEvents ).indexOf( "shutdown" ) !== -1 ) {
      return true;
    }
    return false;
  }

  , isUpdatePending: function () {
    if ( _.values( ongoingEvents ).indexOf( "update" ) !== -1 ) {
      return true;
    }
    return false;
  }

});

PowerStore.dispatchToken = FreeNASDispatcher.register( function ( payload ) {
  var action = payload.action;

  switch ( action.type ) {

    case ActionTypes.UPDATE_SOCKET_STATE:
      // clear ongoingEvents
      ongoingEvents = {};
      PowerStore.emitChange();
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      var args = action.eventData.args;
      var taskID   = args.args["id"];

      if ( UPDATE_MASK.indexOf( args["name"] ) !== -1  ) {
        var updateData = args["args"];

        if ( args["name"] === "power.changed" ) {
          ongoingEvents[taskID] = updateData["operation"];
        } else if ( args["name"] === "update.changed" &&
                    updateData["operation"] === "started" ) {
          ongoingEvents[taskID] = "update";
        }

        PowerStore.emitChange();

      // TODO: Make this more generic, triage it earlier,
      // create ActionTypes for it
      } else if ( args["name"] === "task.updated" &&
                  args.args["state"] === "FINISHED" &&
                  _.keys( ongoingEvents ).indexOf( taskID ) !== -1 ) {
        if ( ongoingEvents[taskID] !== "shutdown" ||
             ongoingEvents[taskID] !== "reboot" ) {
          delete ongoingEvents.taskID;
        }
        PowerStore.emitChange();
      }

      break;

    default:
    // No action
  }
});

module.exports = PowerStore;
