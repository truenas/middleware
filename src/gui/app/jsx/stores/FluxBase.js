// FLUX STORE BASE CLASS
// =====================
// Defines some common methods which all stores implement, and properly extends
// EventEmitter.

"use strict";

import _ from "lodash";
import DL from "../common/DebugLogger";

import { EventEmitter } from "events";

class FluxBaseClass extends EventEmitter {

  constructor () {
    super();
    this.CHANGE_EVENT = "change";
    this.KEY_UNIQUE   = null;
    this.ITEM_LABELS   = null;
    this.ITEM_SCHEMA  = null;
  }

  get uniqueKey () {
    if ( this.KEY_UNIQUE ) {
      return this.KEY_UNIQUE;
    } else {
      throw new Error( "The KEY_UNIQUE for this Flux store was not set:" );
      DL.dir( this );
      return false;
    }
  }

  get itemLabels () {
    if ( this.ITEM_LABELS ) {
      return this.ITEM_LABELS;
    } else {
      throw new Error( "The ITEM_LABELS for this Flux store were not set:" );
      DL.dir( this );
      return false;
    }
  }

  get itemSchema () {
    if ( this.ITEM_SCHEMA ) {
      return this.ITEM_SCHEMA;
    } else {
      throw new Error( "The ITEM_SCHEMA for this Flux store was not defined:" );
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
    let newObject = _.clone( targetObject );

    for ( let prop in newObject ) {
      // Iterate over the enumerable properties of the target object
      if ( keyHash.hasOwnProperty( prop ) ) {
        // One of the desired properties exists on the object
        if ( prop === keyHash[ prop ] ) {
          // The new key and old key are the same
          continue;
        } else {
          // Reassign the value to the new key
          newObject[ keyHash[ prop ] ] = newObject[ prop ];
        }
      }
      // Either the prop wasn't found in the hash, so it's implicitly ignored
      // OR
      // The key has changed, and we're deleting the old one
      delete newObject[ prop ];
    }
    return newObject;
  }

};

export default FluxBaseClass;
