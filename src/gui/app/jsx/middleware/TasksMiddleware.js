// Users Middleware
// ================
// Handle the lifecycle and event hooks for the Users channel of the middleware

"use strict";

import MiddlewareClient from "../middleware/MiddlewareClient";

import TasksActionCreators from "../actions/TasksActionCreators";

module.exports = {

    // There are no subscribe or unsubscribe functions here, because task
    // subscription can be handled directly through the Middleware Client.

    getCompletedTaskHistory: function( callback, offset ) {
      return MiddlewareClient.request(
          "task.query"
        , [[["state","~","FINISHED|ABORTED|FAILED"]]
        , {
            "offset": ( offset || 0 )
          , "limit": 100
          , "sort": "id"
          , "dir": "desc" }] // TODO: Sort dir doesn't work?
        , callback );
    }

  , abortTask: function ( taskID ) {
      MiddlewareClient.request( "task.abort", [parseInt(taskID, 10)]);
    }

};
