// Tasks Tab
// =========

"use strict";

var _      = require("lodash");
var React  = require("react");
var TWBS   = require("react-bootstrap");
var moment = require("moment");

// Middleware
var MiddlewareClient = require("../../middleware/MiddlewareClient");
var MiddlewareStore  = require("../../stores/MiddlewareStore");

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
      var taskIDs = _.sortBy( _.keys( this.props.tasks ) ).reverse();
      return(
        <div className="disclosure-open debug-column-content">
          <h5 className="debug-heading disclosure-toggle">{ this.props.title + " (" + taskIDs.length + ")" }</h5>
          <div className="disclosure-target">
            { taskIDs.map( this.createTask ) }
          </div>
        </div>
      );
    }

});

var Tasks = React.createClass({

    getInitialState: function() {
      return _.assign( {}, MiddlewareStore.getAllTasks() );
    }

  , componentDidMount: function() {
      MiddlewareStore.addChangeListener( this.handleMiddlewareChange );
      MiddlewareClient.subscribe(["task.*"]);
    }

  , componentWillUnmount: function() {
      MiddlewareStore.removeChangeListener( this.handleMiddlewareChange );
      MiddlewareClient.unsubscribe(["task.*"]);
    }

  , handleMiddlewareChange: function() {
      this.setState( _.assign( {}, MiddlewareStore.getAllTasks() ) );
    }

  , render: function() {
      return (
        <div className="debug-content-flex-wrapper">

          <TWBS.Col xs={6} className="debug-column" >
            <TasksSection
              title = { "Created Tasks" }
              tasks = { this.state["CREATED"] } canCancel />
            <TasksSection
              title = { "Waiting Tasks" }
              tasks = { this.state["WAITING"] } paused canCancel />
            <TasksSection
              title = { "Executing Tasks" }
              tasks = { this.state["EXECUTING"] } showProgress canCancel />
            <TasksSection
              title = { "Finished Tasks" }
              tasks = { this.state["FINISHED"] } showProgress />
          </TWBS.Col>

        </div>
      );
    }

});

module.exports = Tasks;
