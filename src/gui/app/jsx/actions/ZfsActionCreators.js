// Zfs.Pool Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class ZfsActionCreators {

  static receiveVolumes ( volumes, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_VOLUMES
      , timestamp
      , volumes
      }
    );
  }

  static receiveAvailableDisks ( disks, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_AVAILABLE_DISKS
      , timestamp
      , disks
      }
    );
  }

  static receivePool ( poolData, poolName, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_VOLUMES
      , timestamp
      , poolData
      , poolName
      }
    );
  }

  static receiveBootPool ( bootPool, poolName, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_BOOT_POOL
      , timestamp
      , bootPool
      , poolName
      }
    );
  }

  static receivePoolDisks ( poolName, poolDisks, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_POOL_DISK_IDS
      , timestamp
      , poolDisks
      , poolName
      }
    );
  }

};

export default ZfsActionCreators;
