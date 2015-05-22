// Groups Middleware
// ================
// Handle the lifecycle and event hooks for the Groups channel of the middleware

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

import GAC from "../actions/GroupsActionCreators";

class GroupsMiddleware extends AbstractBase {

  static subscribe ( componentID ) {
    MC.subscribe( [ "groups.changed" ], componentID );
    MC.subscribe( [ "task.*" ], componentID );
  }

  static unsubscribe ( componentID ) {
    MC.unsubscribe( [ "groups.changed" ], componentID );
    MC.unsubscribe( [ "task.*" ], componentID );
  }

  static requestGroupsList () {
    MC.request( "groups.query"
              , []
              , function handleRequestGroupsList ( groupsList ) {
                  GAC.receiveGroupsList( groupsList );
                }
              );
  }

  static createGroup ( newGroupProps ) {
    MC.request( "task.submit"
              , [ "groups.create" , [ newGroupProps ] ]
              , function handleCreateGroup ( taskID, groupID ) {
                  GAC.receiveGroupUpdateTask( taskID, groupID );
                }
              );
  }

  static updateGroup ( groupID, props ) {
    MC.request( "task.submit"
              , [ "groups.update", [ groupID, props ] ]
              , function handleUpdateGroup ( taskID, GroupID ) {
                  GAC.receiveGroupUpdateTask( taskID, groupID );
                }
              );
  }

  static deleteGroup ( groupID ) {
    MC.request( "task.submit"
              , [ "groups.delete", [ groupID ] ]
              , function handleDeleteGroup ( taskID, groupID ) {
                  GAC.receiveGroupUpdateTask( taskID, groupID );
                }
              );
  }

};

export default GroupsMiddleware;
