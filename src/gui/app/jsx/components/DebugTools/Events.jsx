// Event Log Debug Tab
// ===================

"use strict";

var React  = require("react");
var TWBS   = require("react-bootstrap");
var moment = require("moment");

// Middleware
var MiddlewareClient = require("../../middleware/MiddlewareClient");
var MiddlewareStore  = require("../../stores/MiddlewareStore");

var Events = React.createClass({

    getInitialState: function() {
      return {
          events     : MiddlewareStore.getEventLog()
        , timeFormat : "absolute"
      };
    }

  , componentDidMount: function() {
      MiddlewareStore.addChangeListener( this.handleMiddlewareChange );
      MiddlewareClient.subscribe(["task.*","system.*"]);
    }

  , componentWillUnmount: function() {
      MiddlewareStore.removeChangeListener( this.handleMiddlewareChange );
      MiddlewareClient.unsubscribe(["task.*","system.*"]);
    }

  , handleMiddlewareChange: function( namespace ) {
      var newState = {};

      switch ( namespace ) {
        case "events":
          newState.events = MiddlewareStore.getEventLog();
          break;
      }

      this.setState( newState );
    }

  , handleHumanDateSelect: function( event ) {
      this.setState({ timeFormat: "human" });
    }

  , handleAbsoluteDateSelect: function( event ) {
      this.setState({ timeFormat: "absolute" });
    }

  , createEventLog: function( event, index ) {
      var eventObj  = event.args;
      var timestamp = null;

      if ( this.state.timeFormat === "human" ) {
        timestamp = moment.unix( eventObj.args["timestamp"] ).fromNow();
      } else {
        timestamp = moment.unix( eventObj.args["timestamp"] ).format("YYYY-MM-DD HH:mm:ss");
      }

      return(
        <div className="debug-callout">
          <label>{ eventObj["name"].split(".")[0] }</label>
          <h5>
            { eventObj["name"] }
            <small className="pull-right">{ timestamp }</small>
          </h5>
          <p>{ eventObj.args.description }</p>
          <pre className="debug-monospace-content">
            { JSON.stringify( eventObj.args, null, 2 ) }
          </pre>
        </div>
      );
    }

  , render: function() {
      var logContent = null;

      if ( this.state.events.length ) {
        logContent = this.state.events.map( this.createEventLog );
      } else {
        logContent = <h3 className="text-center">No log content</h3>;
      }

      return (
        <div className="debug-content-flex-wrapper">

          <TWBS.Col xs={6} className="debug-column" >

            <h5 className="debug-heading">System Event Log</h5>
            <div className="debug-column-content">
              { logContent }
            </div>

          </TWBS.Col>

          <TWBS.Col xs={6} className="debug-column" >

            <h5 className="debug-heading">Log Options</h5>
            <div className="debug-column-content well well-sm">
              <div>
                <label style={{ marginRight: "15px" }}>Time Format</label>
                <TWBS.ButtonGroup>
                  <TWBS.Button
                      active  = { this.state.timeFormat === "human" }
                      onClick = { this.handleHumanDateSelect }>
                    {"Relative Time"}
                  </TWBS.Button>
                  <TWBS.Button
                      active  = { this.state.timeFormat === "absolute" }
                      onClick = { this.handleAbsoluteDateSelect }>
                    {"Absolute Date"}
                  </TWBS.Button>
                </TWBS.ButtonGroup>
              </div>
            </div>

          </TWBS.Col>

        </div>
      );
    }

});

module.exports = Events;
