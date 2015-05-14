// Groups Middleware
// ================
// Handle the lifecycle and event hooks for the Groups channel of the middleware

"use strict";

import MiddlewareClient from "../middleware/MiddlewareClient";

import GroupsActionCreators from "../actions/GroupsActionCreators";

module.exports = {

  subscribe: function ( componentID ) {
    MiddlewareClient.subscribe( [ "groups.changed" ], componentID );
    MiddlewareClient.subscribe( [ "task.*" ], componentID );
  }

  , unsubscribe: function ( componentID ) {
    MiddlewareClient.unsubscribe( [ "groups.changed" ], componentID );
    MiddlewareClient.unsubscribe( [ "task.*" ], componentID );
  }

  , requestGroupsList: function () {
    MiddlewareClient.request( "groups.query", [], function ( groupsList ) {
      GroupsActionCreators.receiveGroupsList( groupsList );
    });
  }

  , createGroup: function ( newGroupProps ) {
    MiddlewareClient.request( "task.submit"
                            , [ "groups.create" , [ newGroupProps ] ]
                            , createGroupCallback
                            );
  }

  , createGroupCallback: function ( taskID, groupID ) {
    GroupsActionCreators.receiveGroupUpdateTask( taskID, groupID );
  }

  , updateGroup: function ( groupID, props ) {
    MiddlewareClient.request( "task.submit"
                            , [ "groups.update", [ groupID, props ]]
                            , updateGroupCallback
                            );
  }

  , updateGroupCallback: function ( taskID, GroupID ) {
    GroupsActionCreators.receiveGroupUpdateTask( taskID, groupID );
  }

  , deleteGroup: function ( groupID ) {
    MiddlewareClient.request( "task.submit"
                            , [ "groups.delete", [ groupID ] ]
                            , deleteGroupCallback
                            );
  }

  , deleteGroupCallback: function ( taskID, groupID ) {
    GroupsActionCreators.receiveGroupUpdateTask( taskID, groupID );
  }

};
