// DISKS STORE
// ===========
// Store information about the physical storage devices connected to the FreeNAS
// server, their S.M.A.R.T. status (if available), but not the activity level or
// other highly specific information about the individual components.

"use strict";

import _ from "lodash";

import DL from "../common/DebugLogger";
import ByteCalc from "../common/ByteCalc";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";
import FluxStore from "./FluxBase";

import DisksMiddleware from "../middleware/DisksMiddleware";

const DISK_SCHEMA =
  // Available from disks.query
  { serial       : { type: "string" }
  , byteSize     : { type: "number" }
  , humanSize    : { type: "string" }
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

const DISK_LABELS =
  { serial       : "Serial"
  , humanSize    : "Capacity"
  , online       : "Disk Online"
  , path         : "Path"
  , sectorSize   : "Sector Size"
  , maxRpm       : "Maximum RPM"
  , smartEnabled : "S.M.A.R.T. Enabled"
  , smartStatus  : "S.M.A.R.T. Status"
  , model        : "Disk Model"
  , schema       : "Partition Format"
  };

var _disks = {};

class DisksStore extends FluxStore {

  constructor () {
    super();

    this.dispatchToken = FreeNASDispatcher.register(
      handlePayload.bind( this )
    );

    this.KEY_UNIQUE = "serial";
    this.ITEM_SCHEMA = DISK_SCHEMA;
    this.ITEM_LABELS = DISK_LABELS;
  }

  get disksArray () {
    return (
      _.chain( _disks )
       .values()
       .sortBy( "path" )
       .value()
    );
  }

};

function getCalculatedDiskProps ( disk ) {
  let calculatedProps = {};

  if ( disk.hasOwnProperty( "mediasize" ) ) {
    calculatedProps["humanSize"] = ByteCalc.humanize( disk["mediasize"] );
    // FIXME: TEMPORARY WORKAROUND
    calculatedProps["driveName"] = calculatedProps["humanSize"] + " Drive";
  }

  return calculatedProps;
}

function handlePayload ( payload ) {
  const ACTION = payload.action;

  switch ( ACTION.type ) {

    case ActionTypes.RECEIVE_DISKS_OVERVIEW:
      let newDisks = {};

      ACTION.disksOverview.forEach(
        function iterateDisks ( disk ) {
          newDisks[ disk[ this.KEY_UNIQUE ] ] =
            _.merge( getCalculatedDiskProps( disk )
                   , FluxStore.rekeyForClient( disk, KEY_TRANSLATION )
                   );
        }.bind( this )
      );

      _.merge( _disks, newDisks );
      this.emitChange();
      break;

    case ActionTypes.RECEIVE_DISK_DETAILS:
      if ( _disks.hasOwnProperty( ACTION.diskDetails[ this.KEY_UNIQUE ] ) ) {
        // This disk has already been instantiated, and we should atttempt to
        // patch new information on top of it
        _.merge( _disks[ this.KEY_UNIQUE ]
               , FluxStore.rekeyForClient( ACTION.diskDetails, KEY_TRANSLATION )
               );
      } else {
        // There is no current record for a disk with this identifier, so this
        // will be the initial data.
        _disks[ ACTION.diskDetails[ this.KEY_UNIQUE ] ] =
          FluxStore.rekeyForClient( ACTION.diskDetails, KEY_TRANSLATION );
      }
      this.emitChange();
      break;

    case ActionTypes.MIDDLEWARE_EVENT:
      // TODO: There is currently no correct thing to subscribe to
      break;
  }
}

export default new DisksStore();
