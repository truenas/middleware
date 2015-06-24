// SCHEMA STORE
// ============
// Stores the complete JSON schema provided by the FreeNAS 10 Middleware. Should
// be used for validating submissions to the Middleware Server, formatting Flux
// Stores, and general reference.

"use strict";

import _ from "lodash";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";
import FluxBase from "./FluxBase";

var _schema = {};

class SchemaStore extends FluxBase {

  constructor () {
    super();

    this.dispatchToken = FreeNASDispatcher.register(
      handlePayload.bind( this )
    );
  }

  getDef ( target ) {
    if ( _.has( _schema, [ "definitions", target ] ) ) {
      return _schema.definitions[ target ];
    } else {
      return null;
    }
  }

};

// Handler for payloads from Flux Dispatcher
function handlePayload ( payload ) {
  const ACTION = payload.action;

  switch ( ACTION.type ) {

    case ActionTypes.RECEIVE_MIDDLEWARE_SCHEMAS:
      _schema = ACTION.schemas;
      this.fullUpdateAt = ACTION.timestamp;
      this.emitChange();
      break;
  }
}

export default new SchemaStore();
