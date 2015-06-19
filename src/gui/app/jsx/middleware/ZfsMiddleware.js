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
              , ZAC.receiveVolumes.bind( ZAC )
              );
  }

  // TODO: Deprecated, should be using volumes.* RPC namespaces now
  static requestPool ( poolName ) {
    MC.request( "zfs.pool." + poolName
              , []
              , ZAC.receivePool.bind( ZAC )
              );
  }

  static requestBootPool () {
    MC.request( "zfs.pool.get_boot_pool"
              , []
              , ZAC.receiveBootPool.bind( ZAC )
              );
  }

  static requestPoolDisks ( poolName ) {
    MC.request( "zfs.pool.get_disks"
              , [ poolName ]
              , ZAC.receivePoolDisks.bind( ZAC )
              );
  }

};

export default ZfsMiddleware;
