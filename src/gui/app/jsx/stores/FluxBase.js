// FLUX STORE BASE CLASS
// =====================
// Defines some common methods which all stores implement, and properly extends
// EventEmitter.

"use strict";

import { EventEmitter } from "events";

class FluxBaseClass extends EventEmitter {

  constructor () {
    super();
    this.CHANGE_EVENT = "change";
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
