// Zfs.Pool Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

module.exports = {

    receiveZfsPool: function( zfsPool, zfsPoolName ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type        	: ActionTypes.RECEIVE_ZFS_POOL_DATA
        , zfsPool     	: zfsPool
        , zfsPoolName   : zfsPoolName
      });
    }

  , receiveZfsBootPool: function( zfsBootPool, zfsBootPoolArgument ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type                  : ActionTypes.RECEIVE_ZFS_BOOT_POOL_DATA
        , zfsBootPool           : zfsBootPool
        , zfsBootPoolArgument   : zfsBootPoolArgument
      });
  }

  , receiveZfsPoolGetDisks: function( zfsPoolGetDisks, zfsPoolGetDisksArgument ) {
      FreeNASDispatcher.handleMiddlewareAction({
          type                      : ActionTypes.RECEIVE_ZFS_POOL_GET_DISKS_DATA
        , zfsPoolGetDisks           : zfsPoolGetDisks
        , zfsPoolGetDisksArgument   : zfsPoolGetDisksArgument
      });
  }


};
