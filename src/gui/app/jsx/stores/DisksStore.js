// DISKS STORE
// ===========
// Store information about the physical storage devices connected to the FreeNAS
// server, their S.M.A.R.T. status (if available), but not the activity level or
// other highly specific information about the individual components.

"use strict";

import _ from "lodash";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";
import FluxStore from "./FluxBase";

import DisksMiddleware from "../middleware/DisksMiddleware";

let disks = {};

class DisksStore extends FluxStore {

  constructor () {
    super();

    this.dispatchToken = FreeNASDispatcher.register(
      handlePayload.bind( this )
    );
  }

  getAllDisks () {
    return disks;
  }

};

function handlePayload ( payload ) {
  const ACTION = payload.action;

  switch ( ACTION.type ) {

    case ActionTypes.RECEIVE_DISKS_OVERVIEW:
      ACTION.disksOverview.forEach( disk => disks[ disk.serial ] = disk );
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      // TODO: There is currently no correct thing to subscribe to
      break;
  }
}

export default new DisksStore();
