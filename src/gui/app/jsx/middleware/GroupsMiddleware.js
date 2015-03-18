// Groups Middleware
// ================
// Handle the lifecycle and event hooks for the Groups channel of the middleware

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

var GroupsActionCreators = require("../actions/GroupsActionCreators");

module.exports = {

    subscribe: function() {
      MiddlewareClient.subscribe( ["groups.changed"]);
      MiddlewareClient.subscribe( ["task.*"]);
    }

  , unsubscribe: function() {
      MiddlewareClient.unsubscribe( ["groups.changed"]);
      MiddlewareClient.unsubscribe( ["task.*"]);
    }

  , requestGroupsList: function() {
      MiddlewareClient.request( "groups.query", [], function ( groupsList ) {
        GroupsActionCreators.receiveGroupsList( groupsList );
      });
    }

  , updateGroup: function (groupID, props) {
      MiddlewareClient.request( "task.submit", ["groups.update", [groupID, props]], function ( taskID ) {
        GroupsActionCreators.receiveGroupUpdateTask( taskID, groupID );
      });
    }

};
