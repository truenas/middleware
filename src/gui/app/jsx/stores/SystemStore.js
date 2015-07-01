// System Flux Store
// ----------------

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

var CHANGE_EVENT = "change";

var _systemInfoData = {};
var _systemDeviceData = {};
var _systemGeneralConfig = {};
var _localUpdatePending = [];

var SystemStore = _.assign( {}, EventEmitter.prototype, {

  emitChange: function ( changeType ) {
      this.emit( CHANGE_EVENT );
    }

  , addChangeListener: function ( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function ( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  , getSystemInfo: function ( name ) {
      return _systemInfoData[name];
    }

  , getSystemDevice: function ( name ) {
      return _systemDeviceData[name];
    }

  , getSystemGeneralConfig: function () {
      return _systemGeneralConfig;
    }

  /**
   * Check if there are any pending update tasks.
   * @return {Boolean}
   */
  , isUpdating: function () {
      return _localUpdatePending.length > 0;
    }

});

SystemStore.dispatchToken = FreeNASDispatcher.register( function ( payload ) {
  var action = payload.action;

  switch ( action.type ) {

    case ActionTypes.RECEIVE_SYSTEM_INFO_DATA:
      _systemInfoData[action.systemInfoName] = action.systemInfo;
      SystemStore.emitChange();
      break;
    case ActionTypes.RECEIVE_SYSTEM_DEVICE_DATA:
      _systemDeviceData[action.systemDeviceArgument] = action.systemDevice;
      SystemStore.emitChange();
      break;
    case ActionTypes.RECEIVE_SYSTEM_GENERAL_CONFIG_DATA:
      _systemGeneralConfig = action.config;
      SystemStore.emitChange();
      break;
    case ActionTypes.RECEIVE_SYSTEM_GENERAL_CONFIG_UPDATE:
      _localUpdatePending.push( action.taskID );
      SystemStore.emitChange();
      break;
    case ActionTypes.MIDDLEWARE_EVENT:
      let args = action.eventData.args;
      if ( args.name === "task.updated"
          && args.args.name === "system.general.configure"
          && args.args.state === "FINISHED" ) {
        _localUpdatePending = _.without( _localUpdatePending, args.args.id );
        SystemStore.emitChange();
      }
      break;

    default:
      // No action
      break;
  }
});

module.exports = SystemStore;
