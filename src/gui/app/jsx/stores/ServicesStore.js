// Services Flux Store
// ----------------

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";
import FluxBase from "./FluxBase";

import ServicesMiddleware from "../middleware/ServicesMiddleware";

var CHANGE_EVENT = "change";
var UPDATE_MASK = "services.changed";
var PRIMARY_KEY = "name";

var _services = [];
var _scheduledForStateUpdate = {};

const SERVICES_SCHEMA =
  { type: "object"
  , properties:
    { state:    { enum: [ "running", "stopped", "unknown" ] }
    , pid:      { type: "integer" }
    , id:       { type: "string" }
    , name:     { type: "string" }
    }
  };

const SERVICES_LABELS =
  { state       : "State"
  , pid         : "PID"
  , id          : "Service ID"
  , name        : "Service Name"
  };

class ServicesStore extends FluxBase {

  constructor () {
    super();

    this.dispatchToken = FreeNASDispatcher.register(
      handlePayload.bind( this )
    );

    this.KEY_UNIQUE = "name";
    this.ITEM_SCHEMA = SERVICES_SCHEMA;
    this.ITEM_LABELS = SERVICES_LABELS;
  }

  findServiceByKeyValue ( key, value ) {
    var predicate = {};
    predicate[key] = value;

    return _.find( _services, predicate );
  }

  get services () {
    return _services;
  }

}

function handlePayload ( payload ) {
  const action = payload.action;

  switch ( action.type ) {

    case ActionTypes.RECEIVE_RAW_SERVICES:
      _services = action.rawServices;
      this.emitChange();
      break;

    case ActionTypes.RECEIVE_SERVICE_UPDATE_TASK:
      _scheduledForStateUpdate[ action.taskID ] = action.serviceName;
      this.emitChange();
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      if ( _scheduledForStateUpdate[action.eventData.args.args.id]
           && ( action.eventData.args.args.state === "FINISHED" ||
                action.eventData.args.args.state === "FAILED" ) ) {
        // We have final result lets get the new set of services and
        // clean this task id from _scheduledForStateUpdate
        ServicesMiddleware.requestServicesList();
        _.remove( _scheduledForStateUpdate, action.eventData.args.args.id );
      }
      break;

    default:
    // No action
  }
}

export default new ServicesStore;
