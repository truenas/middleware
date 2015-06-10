// DISKS STORE
// ===========
// Store information about the physical storage devices connected to the FreeNAS
// server, their S.M.A.R.T. status (if available), but not the activity level or
// other highly specific information about the individual components.

"use strict";

import _ from "lodash";

import DL from "../common/DebugLogger";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";
import FluxStore from "./FluxBase";

import DisksMiddleware from "../middleware/DisksMiddleware";

const DISK_SCHEMA =
  // Available from disks.query
  { serial       : { type: "string" }
  , byteSize     : { type: "number" }
  , dateUpdated  : { type: "number" }
  , dateCreated  : { type: "number" }
  , online       : { type: "boolean" }
  , path         : { type: "string" }
  // Available from disks.get_disk_config
  , sectorSize   : { type: "number" }
  , description  : { type: "string" }
  , maxRpm       : { type: "string" }
  // , partitions   : ""
  , smartEnabled : { type: "string" }
  , smartStatus  : { type: "string" }
  , model        : { type: "string" }
  , schema       : { type: "string" }
  };

const KEY_TRANSLATION =
  // Available from disks.query
  { serial          : "serial"
  , mediasize       : "byteSize"
  , "updated-at"    : "dateUpdated"
  , "created-at"    : "dateCreated"
  , online          : "online"
  , path            : "path"
  // Available from disks.get_disk_config
  , sectorsize      : "sectorSize"
  , description     : "description"
  , "max-rotation"  : "maxRpm"
  , "smart-enabled" : "smartEnabled"
  , "smart-status"  : "smartStatus"
  , model           : "model"
  , schema          : "schema"
  };

var disks = {};

class DisksStore extends FluxStore {

  constructor () {
    super();

    this.dispatchToken = FreeNASDispatcher.register(
      handlePayload.bind( this )
    );
    this.KEY_UNIQUE = "serial";
  }

  getDisksArray () {
    return (
      _.chain( disks )
       .values()
       .sortBy( "path" )
       .value()
    )
  }

};

const DISKS_STORE = new DisksStore();

function rekeyForClient ( targetObject, keyHash ) {
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
    // Either the prop wasn't found in the hash, in which case we don't need it,
    // or the key has changed, and we're deleting the old one
    delete targetObject[ prop ];
  }
  return targetObject;
}

function handlePayload ( payload ) {
  const ACTION = payload.action;

  switch ( ACTION.type ) {

    case ActionTypes.RECEIVE_DISKS_OVERVIEW:
      let newDisks = {};

      ACTION.disksOverview.forEach( disk =>
                            newDisks[ disk[ this.KEY_UNIQUE ] ] =
                              rekeyForClient( disk, KEY_TRANSLATION )
                          )
      _.merge( disks, newDisks );
      DISKS_STORE.emitChange();
      break;

    case ActionTypes.RECEIVE_DISK_DETAILS:
      if ( disks.hasOwnProperty( ACTION.diskDetails[ this.KEY_UNIQUE ] ) ) {
        // This disk has already been instantiated, and we should atttempt to
        // patch new information on top of it
        _.merge( disks[ this.KEY_UNIQUE ]
               , rekeyForClient( ACTION.diskDetails, KEY_TRANSLATION )
               );
      } else {
        // There is no current record for a disk with this identifier, so this
        // will be the initial data.
        disks[ ACTION.diskDetails[ this.KEY_UNIQUE ] ] =
          rekeyForClient( ACTION.diskDetails, KEY_TRANSLATION );
      }
      DISKS_STORE.emitChange();
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      // TODO: There is currently no correct thing to subscribe to
      break;
  }
}

export default DISKS_STORE;
