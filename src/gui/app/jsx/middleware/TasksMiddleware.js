// Users Middleware
// ================
// Handle the lifecycle and event hooks for the Users channel of the middleware

"use strict";

import MC from "./MiddlewareClient";
import AbstractBase from "./MiddlewareAbstract";

// There are no subscribe or unsubscribe functions here, because task
// subscription can be handled directly through the Middleware Client.

class TasksMiddleware extends AbstractBase {

  static getCompletedTaskHistory ( callback, offset ) {
    // TODO: This MUST go through the Flux pattern, and needs to be limited
    // by the value set in StoreLimits
    return MC.request( "task.query"
                     , [ [[ "state", "~", "FINISHED|ABORTED|FAILED" ]]
                       , { offset: ( offset || 0 )
                         , limit: 100
                         , sort: "id"
                         , dir: "desc"
                         }
                       ]
                     , callback
                     );
  }

  static abortTask ( taskID ) {
    MC.request( "task.abort", [ parseInt( taskID, 10 ) ] );
  }

};

export default TasksMiddleware;
