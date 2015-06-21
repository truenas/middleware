// Disks Middleware
// ================

"use strict";

import _ from "lodash";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

import DAC from "../actions/DisksActionCreators";

class DisksMiddleware extends AbstractBase {

  static subscribe ( componentID ) {
    MC.subscribe( [ "entity-subscriber.disks.changed" ], componentID );
  }

  static unsubscribe ( componentID ) {
    MC.unsubscribe( [ "entity-subscriber.disks.changed" ], componentID );
  }

  static requestDisksOverview () {
    MC.request( "disks.query"
              , []
              , DAC.receiveDisksOverview.bind( DAC )
              );
  }

  static requestDiskDetails ( diskPath ) {
    if ( _.isString( diskPath ) ) {
      MC.request( "disks.get_disk_config"
                , [ diskPath ]
                , DAC.receiveDiskDetails.bind( DAC )
                );
    } else {
      throw new Error( "The argument for DisksMiddleware.requestDiskDetails "
                     + "must be a string representing a disk's path." );
      return;
    }
  }

};

export default DisksMiddleware;
