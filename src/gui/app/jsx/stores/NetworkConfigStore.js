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

var _localUpdatePending = false;
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

  , isLocalUpdatePending: function () {
      return _localUpdatePending;
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
        let updateData = args.args;

        // The second check here should never fail, but I'm putting it
        // here out of an overabundance of caution.
        let validUpdate = args[ "name" ] === UPDATE_MASK
                        && updateData[ "operation" ] === "update";

        if ( validUpdate ) {
          _localUpdatePending = false;
          NetworkConfigStore.emitChange();
        }

        break;

      case ActionTypes.RECEIVE_NETWORK_UPDATE_TASK:

        _localUpdatePending = true;
        NetworkConfigStore.emitChange();
        break;
    }
  }
);

module.exports = NetworkConfigStore;
