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
              , GAC.receiveGroupsList.bind( GAC )
              );
  }

  static createGroup ( newGroupProps ) {
    MC.request( "task.submit"
              , [ "groups.create" , [ newGroupProps ] ]
              , GAC.receiveGroupUpdateTask.bind( GAC )
              );
  }

  static updateGroup ( groupID, props ) {
    MC.request( "task.submit"
              , [ "groups.update", [ groupID, props ] ]
              , GAC.receiveGroupUpdateTask.bind( GAC )
              );
  }

  static deleteGroup ( groupID ) {
    MC.request( "task.submit"
              , [ "groups.delete", [ groupID ] ]
              , GAC.receiveGroupUpdateTask.bind( GAC )
              );
  }

};

export default GroupsMiddleware;
