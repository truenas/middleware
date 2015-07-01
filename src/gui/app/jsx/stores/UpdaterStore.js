// Updater Flux Store
// ------------------

"use strict";

import _ from "lodash"
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";
import FluxStore from "./FluxBase";

import UpdaterMiddleware from "../middleware/UpdaterMiddleware";


const UPDATE_MASK = [ "update.in_progress", "update.changed" ];
const UPDATE_TASK_MASK = [ "update.configure"
                         , "update.check"
                         , "update.download"
                         , "update.update" ];

class UpdaterStore extends FluxStore {
  constructor () {
    super();

    this.dispatchToken = FreeNASDispatcher.register(
      handlePayload.bind( this )
    );
  }

  get updateMask() {
    return UPDATE_MASK;
  }

}

function handlePayload ( payload ) {
  const action = payload.action;

  switch ( action.type ) {

    case ActionTypes.MIDDLEWARE_EVENT:
      let args = action.eventData.args;
      let taskID = args.args["id"];

      if ( UPDATE_TASK_MASK.indexOf( args[ "name" ] ) !== -1  ) {
        let updateData = args["args"];
        // switch ( args["name"] ) {
        //   case "update.check":
        //     break;
        console.log( "Suraj in UPDATE_MASK printing updateData: ", updateData );
        console.log( "Suraj printing task from getTaskById: "
                   , UpdaterStore.getTaskById( taskId ) );
        this.emitChange();
      } else if ( UPDATE_MASK.indexOf( args[ "name" ] ) !== -1 ) {
        // do something
        console.log( "Suraj in UPDATE_MASK cond" );
      }

  }
};

export default new UpdaterStore();

