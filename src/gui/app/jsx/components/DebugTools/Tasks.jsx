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
      var taskData = this.props.tasks[ taskID ];
      var taskName = _.has( taskData, "name" ) ? ": " + taskData["name"] : "";
      var progress  = null;
      var cancelBtn = null;

      if ( this.props.paused ) {
        progress = <TWBS.ProgressBar active now={ 100 } />;
      } else if ( this.props.showProgress ) {
        progress = <TWBS.ProgressBar
                      now     = { taskData["percentage"] }
                      bsStyle = { taskData["percentage"] === 100 ? "success" : "info" } />;
      }

      if ( this.props.canCancel ) {
        //cancel things here
      }

      return (
        <TWBS.Panel
          bsStyle = "info"
          header  = { "Task " + taskID + taskName } key={ index }>
          { progress }
        </TWBS.Panel>
      );
    }

  , render: function() {
      var taskIDs =  _.keys( this.props.tasks );
      return(
        <div className="disclosure-open">
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
