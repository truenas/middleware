// Zfs.Pool Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class ZfsActionCreators {

  receiveZfsPool ( zfsPool, zfsPoolName ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_ZFS_POOL_DATA
      , zfsPool: zfsPool
      , zfsPoolName: zfsPoolName
      }
    );
  }

  receiveZfsBootPool ( zfsBootPool, zfsBootPoolArgument ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_ZFS_BOOT_POOL_DATA
      , zfsBootPool: zfsBootPool
      , zfsBootPoolArgument: zfsBootPoolArgument
      }
    );
  }

  receiveZfsPoolGetDisks ( zfsPoolGetDisks, zfsPoolGetDisksArgument ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_ZFS_POOL_GET_DISKS_DATA
      , zfsPoolGetDisks: zfsPoolGetDisks
      , zfsPoolGetDisksArgument: zfsPoolGetDisksArgument
      }
    );
  }

};

export default new ZfsActionCreators();
