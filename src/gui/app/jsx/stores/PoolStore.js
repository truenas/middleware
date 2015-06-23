// ZFS POOL STORE
// ==============

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";
import DL from "../common/DebugLogger";
import FluxStore from "./FluxBase";

var _storagePools = {};
var _bootPool     = {};

class PoolStore extends FluxStore {

  constructor () {
    super();

    this.dispatchToken = FreeNASDispatcher.register(
      handlePayload.bind( this )
    );
    // this.KEY_UNIQUE = "serial";
    // this.ITEM_SCHEMA = DISK_SCHEMA;
    // this.ITEM_LABELS = DISK_LABELS;
  }

  get bootPool () {
    return _bootPool;
  }

  listStoragePools ( sortKey ) {
    if ( sortKey ) {
      return _.chain( _storagePools )
              .values()
              .sort( sortKey )
              .value();
    } else {
      return _.values( _storagePools );
    }
  }

  getDisksInPool ( poolName ) {
    if ( _.has( _storagePools, `[ ${ poolName } ].memberDisks` ) ) {
      return _storagePools[ poolName ].memberDisks;
    } else {
      return [];
    }
  }

  getDisksInBootPool () {
    if ( _.has( _bootPool, "memberDisks" ) ) {
      return _bootPool.memberDisks;
    } else {
      return [];
    }
  }

}

// Handler for payloads from Flux Dispatcher
function handlePayload ( payload ) {
  const ACTION = payload.action;

  switch ( ACTION.type ) {

    case ActionTypes.RECEIVE_POOL:
      _storagePools[ ACTION.poolName ] = ACTION.poolData;
      this.emitChange();
      break;

    case ActionTypes.RECEIVE_BOOT_POOL:
      _bootPool = ACTION.bootPool;
      this.emitChange();
      break;

    case ActionTypes.RECEIVE_POOL_DISK_IDS:
      _.merge( _storagePools
             , { [ ACTION.poolName ]: { memberDisks: ACTION.poolDisks } }
             );
      this.emitChange();
      break;

  }
}

export default new PoolStore();
