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



class NetworkConfigStore extends EventEmitter.prototype {

  emitChange () {
    this.emit( CHANGE_EVENT );
  }

  addChangeListener ( callback ) {
    this.on( CHANGE_EVENT, callback );
  }

  removeChangeListener ( callback ) {
    this.removeListener( CHANGE_EVENT, callback );
  }

  getUpdateMask () {
    return UPDATE_MASK;
  }

  isLocalUpdatePending () {
    return _localUpdatePending;
  }

  getNetworkConfig () {
    return _networkConfig;
  }

  dispatchTokenCallback ( payload ) {
    var action = payload.action;

    switch ( action.type ) {

      case ActionTypes.RECEIVE_NETWORK_CONFIG:

        _networkConfig = action.networkConfig;
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
          this.emitChange();
        }

        break;

      case ActionTypes.RECEIVE_NETWORK_UPDATE_TASK:

        _localUpdatePending = true;
        this.emitChange()
        break;
    }
  }

};

NetworkConfigStore.dispatchToken = ( dispatchTokenCallback );

export default new NetworkConfigStore ( );

