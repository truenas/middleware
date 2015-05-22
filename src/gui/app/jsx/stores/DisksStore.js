// DISKS STORE
// ===========
// Store information about the physical storage devices connected to the FreeNAS
// server, their S.M.A.R.T. status (if available), but not the activity level or
// other highly specific information about the individual components.

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

// TODO: This doesn't exist yet.
// import DisksMiddleware from "../middleware/DisksMiddleware";

const CHANGE_EVENT = "change";

class DisksStore extends EventEmitter {

  constructor () {
    super();

    this.dispatchToken = FreeNASDispatcher.register(
      handlePayload.bind( this )
    );

  }
};

function handlePayload ( payload ) {
  const ACTION = payload.action;

  switch ( ACTION.type ) {

    case ActionTypes.RECEIVE_RAW_DISKS:
      // TODO: Disk schema needs to be fixed.
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      // TODO: There is currently no correct thing to subscribe to
      break;
  }
}

export default new DisksStore();
