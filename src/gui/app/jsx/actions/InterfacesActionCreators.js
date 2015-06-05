// Interfaces Action Creators
// ==========================

"use strict";

import FreeNASDispatcher from "../dispatcher/FreeNASDispatcher";
import { ActionTypes } from "../constants/FreeNASConstants";

class InterfacesActionCreators {

  static receiveInterfacesList ( rawInterfacesList ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_INTERFACES_LIST
      , rawInterfacesList: rawInterfacesList
      }
    );
  }

  static receiveInterfaceConfigureTask ( taskID, interfaceName ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes. RECEIVE_INTERFACE_CONFIGURE_TASK
      , taskID: taskID
      , interfaceName: interfaceName
      }
    );
  }


  static receiveUpInterfaceTask ( taskID, interfaceName ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_UP_INTERFACE_TASK
      , taskID: taskID
      , interfaceName: interfaceName
      }
    );
  }

  static receiveDownInterfaceTask ( taskID, interfaceName ) {
    FreeNASDispatcher.handleMiddlewareAction(
      { type: ActionTypes.RECEIVE_DOWN_INTERFACE_TASK
      , taskID: taskID
      , interfaceName: interfaceName
      }
    );
  }

};

export default InterfacesActionCreators;
