// Zfs.Pool Action Creators
// ==================================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class ZfsActionCreators {

  static receivePool ( poolData, poolName ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_POOL
      , poolData
      , poolName
      }
    );
  }

  static receiveBootPool ( bootPool, poolName ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_BOOT_POOL
      , bootPool
      , poolName
      }
    );
  }

  static receivePoolDisks ( poolDisks, poolName ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_POOL_DISK_IDS
      , poolDisks
      , poolName
      }
    );
  }

};

export default ZfsActionCreators;
