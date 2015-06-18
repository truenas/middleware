// ZFS Pool Middleware
// ===================

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";
import ZAC from "../actions/ZfsActionCreators";

class ZfsMiddleware extends AbstractBase {

  static requestPool ( poolName ) {
    MC.request( "zfs.pool." + poolName
              , []
              , function handlePool ( response ) {
                  ZAC.receivePool( response, poolName );
                }
              );
  }

  static requestBootPool () {
    MC.request( "zfs.pool.get_boot_pool"
              , []
              , function handleBootPool ( response ) {
                  ZAC.receiveBootPool( response );
                }
              );
  }

  static requestPoolDisks ( poolName ) {
    MC.request( "zfs.pool.get_disks"
              , [ poolName ]
              , function handlePoolDisks ( response ) {
                  ZAC.receivePoolDisks( response, poolName );
                }
              );
  }

};

export default ZfsMiddleware;
