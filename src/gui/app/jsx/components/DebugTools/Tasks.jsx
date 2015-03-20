// Tasks Tab
// =========

"use strict";

var _      = require("lodash");
var React  = require("react");
var TWBS   = require("react-bootstrap");
var moment = require("moment");

// Middleware
var MiddlewareClient = require("../../middleware/MiddlewareClient");
var TasksStore       = require("../../stores/TasksStore");
var TasksMiddleware  = require("../../middleware/TasksMiddleware");

var TasksSection = React.createClass({

    propTypes: {
        tasks        : React.PropTypes.object.isRequired
      , paused       : React.PropTypes.bool
      , showProgress : React.PropTypes.bool
      , canCancel    : React.PropTypes.bool
    }

  , createTask: function( taskID, index ) {
      var taskData  = this.props.tasks[ taskID ];
      var taskName  = null;
      var progress  = null;
      var cancelBtn = null;
      var started   = taskData["started_at"] ? moment.unix( taskData["started_at"] ).format("YYYY-MM-DD HH:mm:ss") : "--";
      var finished  = taskData["finished_at"] ? moment.unix( taskData["finished_at"] ).format("YYYY-MM-DD HH:mm:ss") : "--";

      if ( _.has( taskData, "name" ) ) {
        taskName = <h5 className="debug-task-title">{ taskData["name"] }</h5>;
      }

      if ( this.props.paused ) {
        progress = <TWBS.ProgressBar
                     active
                     now    = { 100 }
                     label  = "Waiting..." />;
      } else if ( this.props.showProgress ) {
        progress = <TWBS.ProgressBar
                     now       = { taskData["percentage"] }
                     bsStyle   = { taskData["percentage"] === 100 ? "success" : "info" }
                     label     = { taskData["percentage"] === 100 ? "Completed" : "%(percent)s%" } />;
      }

      if ( this.props.canCancel ) {
        cancelBtn = <TWBS.Button
                      bsSize    = "small"
                      className = "debug-task-abort"
                      bsStyle   = "danger">Abort Task</TWBS.Button>;
      }

      return (
        <div
          className = "debug-task-item"
          key       = { index }>
          <div className="debug-task-id">{ taskID }</div>
          <div className="debug-task-details">
            { taskName }
            <div className="clearfix">
              <h6 className="debug-task-timestamp">{"Task Started: " + started }</h6>
              <h6 className="debug-task-timestamp">{"Task Finished: " + finished }</h6>
            </div>
            <hr />
            <div className = "clearfix">
              { cancelBtn }
              { progress }
            </div>
          </div>
        </div>
      );
    }

  , render: function() {
      var taskIDs = _.sortBy( _.keys( this.props.tasks ), ["id"] ).reverse();
      return(
        <div className="debug-column-content">
          { taskIDs.map( this.createTask ) }
        </div>
      );
    }

});

var Tasks = React.createClass({

    getInitialState: function() {
      return _.assign( {}, TasksStore.getAllTasks() );
    }

  , init: function( tasks ) {
      var historicalTasks = {};

      tasks.forEach( function( task ){
        historicalTasks[ task["id"] ] = task;
        historicalTasks[ task["id"] ]["percentage"] = 100;
      });

      this.setState( _.merge( {}, { "FINISHED": historicalTasks }, TasksStore.getAllTasks() ) );
    }

  , componentDidMount: function() {
      TasksStore.addChangeListener( this.handleMiddlewareChange );
      MiddlewareClient.subscribe(["task.*"]);

      TasksMiddleware.getCompletedTaskHistory( this.init, this.state["FINISHED"].length || 0 );
    }

  , componentWillUnmount: function() {
      TasksStore.removeChangeListener( this.handleMiddlewareChange );
      MiddlewareClient.unsubscribe(["task.*"]);
    }

  , handleMiddlewareChange: function() {
      this.setState( _.merge( {}, { "FINISHED": this.state["FINISHED"] }, TasksStore.getAllTasks() ) );
    }

  , render: function() {
      return (
        <div className="debug-content-flex-wrapper">

          <TWBS.Col xs={6} className="debug-column" >
            <h5 className="debug-heading">{  "Created Tasks (" + _.keys( this.state["CREATED"] ).length + ")" }</h5>
            <TasksSection
              tasks = { this.state["CREATED"] } canCancel />

            <h5 className="debug-heading">{  "Waiting Tasks (" + _.keys( this.state["WAITING"] ).length + ")" }</h5>
            <TasksSection
              tasks = { this.state["WAITING"] } paused canCancel />

            <h5 className="debug-heading">{  "Executing Tasks (" + _.keys( this.state["EXECUTING"] ).length + ")" }</h5>
            <TasksSection
              tasks = { this.state["EXECUTING"] } showProgress canCancel />
          </TWBS.Col>
          <TWBS.Col xs={6} className="debug-column" >
            <h5 className="debug-heading">{  "Completed Task History" }</h5>
            <TasksSection
              tasks = { this.state["FINISHED"] } showProgress />
          </TWBS.Col>

        </div>
      );
    }

});

module.exports = Tasks;
