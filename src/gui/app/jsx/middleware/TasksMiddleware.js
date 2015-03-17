// Users Middleware
// ================
// Handle the lifecycle and event hooks for the Users channel of the middleware

"use strict";

var MiddlewareClient = require("../middleware/MiddlewareClient");

var TasksActionCreators = require("../actions/TasksActionCreators");

module.exports = {

    // There are no subscribe or unsubscribe functions here, because task
    // subscription can be handled directly through the Middleware Client.

    getTasks: function( ids ) {
      MiddlewareClient.request( "task.query", [], function( tasks ) {
        TasksActionCreators.receiveTaskHistory( tasks );
      });
    }

};
