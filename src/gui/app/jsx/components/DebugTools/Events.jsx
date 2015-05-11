// Event Log Debug Tab
// ===================

"use strict";

var componentLongName = "Debug Tools - Events Tab";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";
import moment from "moment";

// Middleware
import MiddlewareClient from "../../middleware/MiddlewareClient";
import MiddlewareStore from "../../stores/MiddlewareStore";

var defaultPredicate = {
    "Object" : "{ \"args\": { \"args\": { \"percentage\": 100 } } }"
  , "String" : "String to search for"
  , "RegExp" : "[ \"pattern\", \"flags\" ]"
};

var Events = React.createClass({

    getInitialState: function () {
      return {
          events           : MiddlewareStore.getEventLog()
        , timeFormat       : "absolute"
        , predicate        : defaultPredicate["Object"]
        , predicateType    : "Object"
        , appliedPredicate : null
      };
    }

  , componentDidMount: function () {
      MiddlewareStore.addChangeListener( this.handleMiddlewareChange );
      MiddlewareClient.subscribe( ["task.*","system.*"], componentLongName );
    }

  , componentWillUnmount: function () {
      MiddlewareStore.removeChangeListener( this.handleMiddlewareChange );
      MiddlewareClient.unsubscribe( ["task.*","system.*"], componentLongName );
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

  , handlePredicateChange: function( event ) {
      this.setState({
          predicate        : event.target.value
        , appliedPredicate : null
      });
    }

  , toggleFilter: function( event ) {
      this.setState({ appliedPredicate : this.state.appliedPredicate ? null : this.state.predicate });
  }

  , switchPredicateType: function( predicateType ) {
      this.setState({
          appliedPredicate : null
        , predicateType    : predicateType
        , predicate        : defaultPredicate[ predicateType ]
      });
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
        <div
          className = "debug-callout"
          key       = { index } >
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

  , getPredicateHelp: function( predicateType ) {
      switch( predicateType ) {
        case "Object":
          return ( <span>In "Object" mode, the "Filter Predicate" field uses <code>_.where()</code> from <a href="http://devdocs.io/lodash/index#where" target="_blank">lodash</a>, and will return matching entries that satisfy the object comparison. Remember, most <code>event</code> objects store their data in the following format: <code>{"{ args: { args: { /* data is here */ } } }"}</code></span> );

        case "String":
          return ( <span>In "String" mode, each event entry is converted by <code>JSON.stringify()</code>, into a string, and then the string entered in the "Filter Predicate" field is used as a substring match.</span> );

        case "RegExp":
          return ( <span>In "String" mode, each event entry is converted by <code>JSON.stringify()</code>, into a string, and then the array entered in the "Filter Predicate" field is used to construct a new <code>RegExp</code> that will test each string. The first value in the array should be your RegExp test string, and the second is (optionally) the flags (<code>g</code>, <code>i</code>, etc.) to use.</span> );

      }
    }

  , render: function () {
      var filteredEventLog = [];
      var logContent       = null;

      if ( this.state.appliedPredicate ) {
        switch ( this.state.predicateType ) {
          case "Object":
            try {
              filteredEventLog = _.where( this.state.events, JSON.parse( this.state.predicate ) );
            }
            catch ( error ) {
              window.alert( "The entered text could not be parsed as an object", error );
            }
            break;

          case "String":
            try {
              filteredEventLog = _.filter( this.state.events, function( eventData ) {
                return JSON.stringify( eventData ).indexOf( this.state.predicate ) !== -1;
              }.bind(this) );
            }
            catch ( error ) {
              window.alert( error );
            }
            break;

          case "RegExp":
            try {
              var reInput = JSON.parse( this.state.predicate );
              var re = new RegExp( reInput[0], reInput[1] ? reInput[1] : "" );
              filteredEventLog = _.filter( this.state.events, function( eventData ) {
                return re.test( JSON.stringify( eventData ) );
              });
            }
            catch ( error ) {
              window.alert( error );
            }
            break;
        }
      }

      if ( filteredEventLog.length ) {
        logContent = filteredEventLog.map( this.createEventLog );
      } else if ( this.state.events.length ) {
        logContent = this.state.events.map( this.createEventLog );
      } else {
        logContent = <h3 className="text-center">No log content</h3>;
      }

      return (
        <div className="debug-content-flex-wrapper">

          <TWBS.Col xs={6} className="debug-column" >

            <h5 className="debug-heading">FreeNAS Event Log</h5>
            <div className="debug-column-content">
              { logContent }
            </div>

          </TWBS.Col>

          <TWBS.Col xs={6} className="debug-column" >

            <h5 className="debug-heading">Options</h5>
            <div className="debug-column-content well well-sm">

              <form className="form-horizontal">

                <TWBS.Input
                  type             = "text"
                  value            = { this.state.predicate }
                  onChange         = { this.handlePredicateChange }
                  label            = "Filter Predicate"
                  labelClassName   = "col-xs-2"
                  wrapperClassName = "col-xs-10"
                  buttonBefore = {
                    <TWBS.DropdownButton
                      bsStyle  = "default"
                      title    = { this.state.predicateType }
                      >
                      <TWBS.MenuItem
                        onClick  = { this.switchPredicateType.bind( null, "Object" ) }
                      >
                        Object
                      </TWBS.MenuItem>
                      <TWBS.MenuItem
                        onClick  = { this.switchPredicateType.bind( null, "String" ) }
                      >
                        String
                      </TWBS.MenuItem>
                      <TWBS.MenuItem
                        onClick  = { this.switchPredicateType.bind( null, "RegExp" ) }
                      >
                        RegExp
                      </TWBS.MenuItem>
                    </TWBS.DropdownButton>
                  }
                  buttonAfter = {
                    <TWBS.Button
                      bsStyle  = { this.state.appliedPredicate ? "success" : "primary" }
                      onClick  = { this.toggleFilter }
                      active   = { !!this.state.appliedPredicate }
                      >
                      { this.state.appliedPredicate ? "Remove Filter" : "Apply Filter" }
                    </TWBS.Button>
                  } />

                <TWBS.Col xs={ 10 } xsOffset={ 2 }>
                  <small>{ this.getPredicateHelp( this.state.predicateType ) }</small>
                </TWBS.Col>

                <div className="form-group">
                  <label className="control-label col-xs-2">Time Format</label>
                  <TWBS.Col xs={ 10 }>
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
                  </TWBS.Col>
                </div>

              </form>

            </div>

          </TWBS.Col>

        </div>
      );
    }

});

module.exports = Events;
