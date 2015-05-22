// ZFS Pool Middleware
// ===================

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";
import ZAC from "../actions/ZfsActionCreators";

class ZfsMiddleware extends AbstractBase {

  static requestZfsPool ( poolName ) {
    MC.request( "zfs.pool." + poolName
              , []
              , function handleZfsPool ( response ) {
                  ZAC.receiveZfsPool( response, poolName );
                }
              );
  }

  static requestZfsBootPool ( bootPoolArg ) {
    MC.request( "zfs.pool.get_disks"
              , [ bootPoolArg ]
              , function handleZfsBootPool ( response ) {
                  ZAC.receiveZfsBootPool( response, bootPoolArg );
                }
              );
  }

  static requestZfsPoolGetDisks ( zfsPoolArg ) {
    MC.request( "zfs.pool.get_disks"
              , [ zfsPoolArg ]
              , function handleZfsPoolDisks ( response ) {
                  ZAC.receiveZfsPoolGetDisks( response, zfsPoolArg );
                }
              );
  }

};

export default ZfsMiddleware;
