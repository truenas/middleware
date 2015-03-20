// Users Middleware
// ================
// Handle the lifecycle and event hooks for the Users channel of the middleware

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

var TasksActionCreators = require("../actions/TasksActionCreators");

module.exports = {

    // There are no subscribe or unsubscribe functions here, because task
    // subscription can be handled directly through the Middleware Client.

    getCompletedTaskHistory: function( callback, offset ) {
      return MiddlewareClient.request(
          "task.query"
        , [[["state","=","FINISHED"]]
        , {
            "offset": ( offset || 0 )
          , "limit": 100
          , "sort": "id"
          , "dir": "desc" }] // TODO: Sort dir doesn't work?
        , callback );
    }

};
