// Tasks Tab
// =========

"use strict";

var componentLongName = "Debug Tools - Tasks Tab";

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
      var abortable = false;

      if ( typeof this.props.canCancel === "undefined" && taskData["abortable"] ) {
        abortable = true;
      }

      if ( _.has( taskData, "name" ) ) {
        taskName = <h5 className="debug-task-title">{ taskData["name"] }</h5>;
      }

      if ( this.props.showProgress ) {
        var progressprops     = {};
        progressprops.now     = taskData["percentage"];
        progressprops.bsStyle = "info";
        progressprops.label   = "%(percent)s%";
        switch ( taskData["state"] ) {
          case "WAITING":
            progressprops.active  = true;
            progressprops.now     = 100;
            progressprops.label   = "Waiting...";
            break;
          case "FINISHED":
            progressprops.bsStyle = "success";
            progressprops.label   = "Completed";
            break;
          case "FAILED":
            progressprops.bsStyle = "danger";
            progressprops.label   = "Failed";
            break;
          case "ABORTED":
            progressprops.bsStyle = "warning";
            progressprops.label   = "Aborted";
            break;
        }
        progress = <TWBS.ProgressBar {...progressprops} />;
      }

      this.callAbort = function () {
        TasksMiddleware.abortTask( taskID );
      };

      if ( this.props.canCancel || abortable ) {
        cancelBtn = <TWBS.Button
                      bsSize    = "small"
                      className = "debug-task-abort"
                      bsStyle   = "danger"
                      onClick   = { this.callAbort }>Abort Task</TWBS.Button>;
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
      var histFinished    = {};
      var histFailed      = {};
      var histAborted     = {};

      tasks.forEach( function( task ){
        switch ( task["state"] ) {
          case "FINISHED":
            histFinished[ task["id"] ] = task;
            histFinished[ task["id"] ]["percentage"] = 100;
            break;
          case "FAILED":
            histFailed[ task["id"] ] = task;
            histFailed[ task["id"] ]["percentage"] = task["percentage"] ? task["percentage"] : 50;
            break;
          case "ABORTED":
            histAborted[ task["id"] ] = task;
            histAborted[ task["id"] ]["percentage"] = task["percentage"] ? task["percentage"] : 50;
            break;
        }
      });

      this.setState( _.merge( {}, { "FINISHED": histFinished }, { "FAILED": histFailed },
        { "ABORTED": histAborted }, TasksStore.getAllTasks() ) );
    }

  , componentDidMount: function() {
      TasksStore.addChangeListener( this.handleMiddlewareChange );
      MiddlewareClient.subscribe( ["task.*"], componentLongName );

      var totalLength = 0;

      _.forEach( this.state, function ( category, index ) {
        totalLength += _.keys( this.state[ category ] ).length;
      }, this );

      TasksMiddleware.getCompletedTaskHistory( this.init, totalLength );
    }

  , componentWillUnmount: function() {
      TasksStore.removeChangeListener( this.handleMiddlewareChange );
      MiddlewareClient.unsubscribe( ["task.*"], componentLongName );
    }

  , handleMiddlewareChange: function() {
      this.setState( _.merge( {}, { "FINISHED": this.state["FINISHED"] },
      { "FAILED": this.state["FAILED"] }, { "ABORTED": this.state["ABORTED"] }, TasksStore.getAllTasks() ) );
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
              tasks = { this.state["WAITING"] } showProgress canCancel />

            <h5 className="debug-heading">{  "Executing Tasks (" + _.keys( this.state["EXECUTING"] ).length + ")" }</h5>
            <TasksSection
              tasks = { this.state["EXECUTING"] } showProgress />
          </TWBS.Col>
          <TWBS.Col xs={6} className="debug-column" >
            <h5 className="debug-heading">{  "Finished Task History" }</h5>
            <TasksSection
              tasks = { this.state["FINISHED"] } showProgress canCancel = {false} />
            <h5 className="debug-heading">{  "Failed Task History" }</h5>
            <TasksSection
              tasks = { this.state["FAILED"] } showProgress canCancel = {false} />
            <h5 className="debug-heading">{  "Aborted Task History" }</h5>
            <TasksSection
              tasks = { this.state["ABORTED"] } showProgress canCancel = {false} />
          </TWBS.Col>

        </div>
      );
    }

});

module.exports = Tasks;
