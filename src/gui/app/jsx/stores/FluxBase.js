// FLUX STORE BASE CLASS
// =====================
// Defines some common methods which all stores implement, and properly extends
// EventEmitter.

"use strict";

import DL from "../common/DebugLogger";

import { EventEmitter } from "events";

class FluxBaseClass extends EventEmitter {

  constructor () {
    super();
    this.CHANGE_EVENT = "change";
    this.KEY_UNIQUE   = "";
  }

  getUniqueKey () {
    if ( this.KEY_UNIQUE ) {
      return this.KEY_UNIQUE;
    } else {
      throw new Error( "The KEY_UNIQUE for this Flux store has not been set:" );
      DL.dir( this );
      return false;
    }
  }

  emitChange ( changeMask ) {
    this.emit( this.CHANGE_EVENT, changeMask );
  }

  addChangeListener ( callback ) {
    this.on( this.CHANGE_EVENT, callback );
  }

  removeChangeListener ( callback ) {
    this.removeListener( this.CHANGE_EVENT, callback );
  }

};

export default FluxBaseClass;
