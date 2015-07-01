// Network Config Flux Store
// =========================

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

import NetworkConfigMiddleware from "../middleware/GroupsMiddleware";

const CHANGE_EVENT = "change";
const UPDATE_MASK = "network.changed";

var _localUpdatePending = [];
var _networkConfig = {};


var NetworkConfigStore = _.assign( {}, EventEmitter.prototype, {

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

  /**
   * Check if there are any pending update tasks.
   * @return {Boolean}
   */
  , isUpdating: function () {
      return _localUpdatePending.length > 0;
    }

  , getNetworkConfig: function () {
      return _networkConfig;
    }

});

NetworkConfigStore.dispatchToken = FreeNASDispatcher.register(
  function ( payload ) {
    var action = payload.action;

    switch ( action.type ) {
      case ActionTypes.RECEIVE_NETWORK_CONFIG:
        _networkConfig = action.networkConfig;
        NetworkConfigStore.emitChange();
        break;

      case ActionTypes.MIDDLEWARE_EVENT:
        let args = action.eventData.args;
        if ( args.name === "task.updated"
            && args.args.name === "network.configure"
            && args.args.state === "FINISHED" ) {
          _localUpdatePending = _.without( _localUpdatePending, args.args.id );
          NetworkConfigStore.emitChange();
        }
        break;

      case ActionTypes.RECEIVE_NETWORK_CONFIG_UPDATE:
        _localUpdatePending.push( action.taskID );
        NetworkConfigStore.emitChange();
        break;
    }
  }
);

module.exports = NetworkConfigStore;
