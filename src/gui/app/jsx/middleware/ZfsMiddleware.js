// ZFS Pool Middleware
// ===================

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";
import ZAC from "../actions/ZfsActionCreators";

class ZfsMiddleware extends AbstractBase {

  static subscribe ( componentID ) {
    MC.subscribe( [ "entity-subscriber.volumes.changed" ]
                , componentID
                );
  }

  static unsubscribe ( componentID ) {
    MC.unsubscribe( [ "entity-subscriber.volumes.changed" ]
                  , componentID
                  );
  }

  static requestVolumes () {
    MC.request( "volumes.query"
              , []
              , function handleVolumes ( response ) {
                  ZAC.receiveVolumes( response );
                }
              );
  }

  // TODO: Deprecated, should be using volumes.* RPC namespaces now
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
