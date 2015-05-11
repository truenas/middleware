// Zfs Flux Store
// ----------------

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

var CHANGE_EVENT = "change";

var _zfsPoolData = {};
var _zfsBootPoolData = {};
var _zfsPoolGetDisksData = {};


var ZfsStore = _.assign( {}, EventEmitter.prototype, {

    emitChange: function(changeType) {
      this.emit( CHANGE_EVENT );
    }

  , addChangeListener: function( callback ) {
      this.on( CHANGE_EVENT, callback );
    }

  , removeChangeListener: function( callback ) {
      this.removeListener( CHANGE_EVENT, callback );
    }

  , getZfsPool: function(name) {
      return _zfsPoolData[name];
    }
  , getZfsBootPool: function(name) {
      return _zfsBootPoolData[name];
  }
  , getZfsPoolGetDisks: function(name) {
      return _zfsPoolGetDisksData[name];
  }



});

ZfsStore.dispatchToken = FreeNASDispatcher.register( function( payload ) {
  var action = payload.action;

  switch( action.type ) {

    case ActionTypes.RECEIVE_ZFS_POOL_DATA:
      _zfsPoolData[action.zfsPoolName] = action.zfsPool;
      ZfsStore.emitChange();
      break;

    case ActionTypes.RECEIVE_ZFS_BOOT_POOL_DATA:
      _zfsBootPoolData[action.zfsBootPoolArgument] = action.zfsBootPool;
      ZfsStore.emitChange();
      break;

    case ActionTypes.RECEIVE_ZFS_POOL_GET_DISKS_DATA:
      _zfsPoolGetDisksData[action.zfsPoolGetDisksArgument] = action.zfsPoolGetDisks;
      ZfsStore.emitChange();
      break;

    default:
      // No action
  }
});

module.exports = ZfsStore;