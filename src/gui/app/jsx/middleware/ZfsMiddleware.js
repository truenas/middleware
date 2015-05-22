// ZFS Pool Middleware
// ===================

"use strict";

import MiddlewareClient from "./MiddlewareClient";
import ZfsActionCreators from "../actions/ZfsActionCreators";

module.exports = {

   requestZfsPool: function(zfsPoolName) {
      MiddlewareClient.request( "zfs.pool." + zfsPoolName,  [], function ( zfsPool ) {
        ZfsActionCreators.receiveZfsPool( zfsPool, zfsPoolName );
      });
  }

 , requestZfsBootPool: function(zfsBootPoolArgument) {
      MiddlewareClient.request( "zfs.pool.get_disks" ,  [zfsBootPoolArgument], function ( zfsBootPool ) {
        ZfsActionCreators.receiveZfsBootPool( zfsBootPool, zfsBootPoolArgument );
      });
  }

 , requestZfsPoolGetDisks: function(zfsPoolGetDisksArgument) {
      MiddlewareClient.request( "zfs.pool.get_disks" ,  [zfsPoolGetDisksArgument], function ( zfsPoolGetDisks ) {
        ZfsActionCreators.receiveZfsPoolGetDisks( zfsPoolGetDisks, zfsPoolGetDisksArgument );
      });
  }


};