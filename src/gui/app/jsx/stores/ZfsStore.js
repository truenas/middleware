// Zfs Flux Store
// ----------------

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";
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

  getZfsPool ( name ) {
    return this._storagePools[ name ];
  }

  getZfsBootPool ( name ) {
    return this._bootPool[ name ];
  }

  getZfsPoolGetDisks ( name ) {
    return this._poolDisks[ name ];
  }

}

// Handler for payloads from Flux Dispatcher
function handlePayload ( payload ) {
  const ACTION = payload.action;

  switch ( ACTION.type ) {

    case ActionTypes.RECEIVE_ZFS_POOL_DATA:
      this._storagePools[ ACTION.zfsPoolName ] = ACTION.zfsPool;
      this.emitChange();
      break;

    case ActionTypes.RECEIVE_ZFS_BOOT_POOL_DATA:
      this._bootPool[ ACTION.zfsBootPoolArgument ] = ACTION.zfsBootPool;
      this.emitChange();
      break;

    case ActionTypes.RECEIVE_ZFS_POOL_GET_DISKS_DATA:
      this._poolDisks[ ACTION.zfsPoolGetDisksArgument ] = ACTION.zfsPoolGetDisks;
      this.emitChange();
      break;

  }
}

export default new ZfsStore();
