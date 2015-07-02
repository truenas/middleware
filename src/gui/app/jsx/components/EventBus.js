// GLOBAL EVENT BUS
// =====================
// Small event bus to assist with propagating events across the entire app, and
// between components which have no parent-child relationship.

"use strict";

import _ from "lodash";
import { EventEmitter } from "events";

let activeNamespaces = new Set();

class EventBus extends EventEmitter {

  constructor () {
    super();

    console.log( this );
  }

  emitToggle () {
    this.emit( "toggle" );
  }

  addListener ( callback ) {
    this.on( "toggle", callback );
  }

  removeListener ( callback ) {
    this.removeListener( "toggle", callback );
  }

}

export default new EventBus();
