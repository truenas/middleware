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

  static rekeyForClient ( targetObject, keyHash ) {
    // Clone target object with all properties, including those we won't keep
    for ( let prop in targetObject ) {
      // Iterate over the enumerable properties of the target object
      if ( keyHash.hasOwnProperty( prop ) ) {
        // One of the desired properties exists on the object
        if ( prop === keyHash[ prop ] ) {
          // The new key and old key are the same
          continue;
        } else {
          // Reassign the value to the new key
          targetObject[ keyHash[ prop ] ] = targetObject[ prop ];
        }
      }
      // Either the prop wasn't found in the hash, so it's implicitly ignored
      // OR
      // The key has changed, and we're deleting the old one
      delete targetObject[ prop ];
    }
    return targetObject;
  }

};

export default FluxBaseClass;
