// Updater Flux Store
// ------------------

"use strict"

import _ from "lodash"
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";
import FluxStore from "./FluxBase";

import UpdaterMiddleware from "../middleware/UpdaterMiddleware";

var CHANGE_EVENT = "change";
var UPDATE_MASK = [ "update.changed", "update.check" ];

var ongoingEvents = {};

class UpdaterStore extends FluxStore {
  constructor () {
    super();

  this.dispatchToken = FreeNASDispatcher.register(
    handlePayload.bind( this )
  );

  get updateMask() {
    return UPDATE_MASK;
  }

  get pendingUpdateIDs() {
    return _updatedOnServer;
  }

  isLocalTaskPending ( id ) {
    return _.values( _localUpdatePending ).indexOf( id ) > -1;
  }
}

function handlePayload ( payload ) {
  const action = payload.action;

  switch ( action.type ) {

    case ActionTypes.MIDDLEWARE_EVENT:
      var args = action.eventData.args;
      var taskID = args.args["id"];

      if ( UPDATE_MASK.indexOf( args["name"] ) !== -1  ) {
        var updateData = args["args"];

        switch ( args["name"] ) {

          case "update.check":



      UpdaterStore.emitChange();
      break;

    default:
    // No action
  }
};

export default new UpdaterStore();

