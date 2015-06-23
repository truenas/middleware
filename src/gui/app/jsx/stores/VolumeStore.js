// VOLUMES STORE
// =============

"use strict";


import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";
import DL from "../common/DebugLogger";
import FluxStore from "./FluxBase";

var _volumes        = {};
var _availableDisks = new Set();

class VolumeStore extends FluxStore {

  constructor () {
    super();

    this.dispatchToken = FreeNASDispatcher.register(
      handlePayload.bind( this )
    );
  }

  get availableDisks() {
    return _.sortBy( Array.from( _availableDisks ) );
  }

  listVolumes ( sortKey ) {
    if ( sortKey ) {
      return _.chain( _volumes )
              .values()
              .sortBy( sortKey )
              .value();
    } else {
      return _.values( _volumes );
    }
  }

}

// Handler for payloads from Flux Dispatcher
function handlePayload ( payload ) {
  const ACTION = payload.action;

  switch ( ACTION.type ) {

    case ActionTypes.RECEIVE_VOLUMES:
      _volumes = ACTION.volumes;
      this.fullUpdateAt = ACTION.timestamp;
      this.emitChange( "volumes" );
      break;

    case ActionTypes.RECEIVE_AVAILABLE_DISKS:
      _availableDisks = new Set( ACTION.disks );
      this.emitChange( "availableDisks" );
      break;

  }
}

export default new VolumeStore();
