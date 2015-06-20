// VOLUMES STORE
// =============

"use strict";


import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";
import DL from "../common/DebugLogger";
import FluxStore from "./FluxBase";

var _volumes = {};

class VolumeStore extends FluxStore {

  constructor () {
    super();

    this.dispatchToken = FreeNASDispatcher.register(
      handlePayload.bind( this )
    );
  }

  listVolumes ( sortKey ) {
    if ( sortKey ) {
      return _.chain( _volumes )
              .values()
              .sort( sortKey )
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
      this._volumes = ACTION.volumes;
      this.fullUpdateAt = ACTION.timestamp;
      this.emitChange();
      break;

  }
}

export default new VolumeStore();
