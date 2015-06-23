// Interfaces Action Creators
// ==========================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class InterfacesActionCreators {

  static receiveInterfacesList ( rawInterfacesList, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_INTERFACES_LIST
      , timestamp
      , rawInterfacesList
      }
    );
  }

  static receiveInterfaceConfigureTask ( interfaceName, taskID, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes. RECEIVE_INTERFACE_CONFIGURE_TASK
      , timestamp
      , taskID
      , interfaceName
      }
    );
  }


  static receiveUpInterfaceTask ( interfaceName, taskID, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_UP_INTERFACE_TASK
      , timestamp
      , taskID
      , interfaceName
      }
    );
  }

  static receiveDownInterfaceTask ( interfaceName, taskID, timestamp ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_DOWN_INTERFACE_TASK
      , timestamp
      , taskID
      , interfaceName
      }
    );
  }

};

export default InterfacesActionCreators;
