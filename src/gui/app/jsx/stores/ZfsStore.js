// Zfs Flux Store
// ----------------

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";
import DL from "../common/DebugLogger";
import FluxStore from "./FluxBase";

class ZfsStore extends FluxStore {

  constructor () {
    super();

    this.dispatchToken = FreeNASDispatcher.register(
      handlePayload.bind( this )
    );
    // this.KEY_UNIQUE = "serial";
    // this.ITEM_SCHEMA = DISK_SCHEMA;
    // this.ITEM_LABELS = DISK_LABELS;

    this._storagePools = {};
    this._bootPool     = {};
    this._poolDisks    = {};
  }

  get bootPool () {
    return this._bootPool;
  }

  getDisksInPool ( poolName ) {
    return this._poolDisks[ poolName ];
  }

}

// Handler for payloads from Flux Dispatcher
function handlePayload ( payload ) {
  const ACTION = payload.action;

  switch ( ACTION.type ) {

    case ActionTypes.RECEIVE_POOL:
      this._storagePools[ ACTION.poolName ] = ACTION.poolData;
      this.emitChange();
      break;

    case ActionTypes.RECEIVE_BOOT_POOL:
      this._bootPool = ACTION.bootPool;
      this.emitChange();
      break;

    case ActionTypes.RECEIVE_POOL_DISK_IDS:
      this._poolDisks[ ACTION.poolName ] = ACTION.poolDisks;
      this.emitChange();
      break;

  }
}

export default new ZfsStore();
