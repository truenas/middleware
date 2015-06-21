// RPC Debug Tab
// =============

"use strict";

import React from "react";
import TWBS from "react-bootstrap";
import _ from "lodash";

// Middleware
import MiddlewareClient from "../../middleware/MiddlewareClient";
import MiddlewareStore from "../../stores/MiddlewareStore";

// freeNASUtil
import freeNASUtil
  from "../../common/freeNASUtil";

// Disclosure Triangles
import DiscTri from "../common/DiscTri";

// Fuzzy TypeAhead
import FuzzyTypeAhead from "../common/FuzzyTypeAhead";


var RPC = React.createClass(

  { getInitialState: function ( ) {
      return { services          : MiddlewareStore.getAvailableRPCServices()
             , methods           : MiddlewareStore.getAvailableRPCMethods()
             , submissionPending : false
             , results           : []
             , methodValue       : ""
             , argsValue         : "[]"
             , anErrorOccurred    : false
             , RPCTraceback      : ""
      };
    }

  , componentDidMount: function ( ) {
      MiddlewareStore.addChangeListener( this.handleMiddlewareChange );
      MiddlewareClient.getServices();
    }

  , componentWillUnmount: function ( ) {
      MiddlewareStore.removeChangeListener( this.handleMiddlewareChange );
    }

  , componentDidUpdate: function ( prevProps, prevState ) {
      if ( ( this.state.submissionPending !== prevState.submissionPending ) &&
           window ) {
        let progressNode = React.findDOMNode( this.refs.pendingProgressBar );
        if ( this.state.submissionPending ) {
          this.progressDisplayTimeout = setTimeout( function ( ) {
            Velocity( progressNode
                    , "fadeIn"
                    , { duration: 500 } );
          }, 500 );
        } else {
          clearTimeout( this.progressDisplayTimeout );
          Velocity( progressNode
                  , "fadeOut"
                  , { duration: 250 } );
        }
      }
    }

  , handleMiddlewareChange: function ( namespace ) {
      var newState = {};

      switch ( namespace ) {
        case "services":
          var availableServices = MiddlewareStore.getAvailableRPCServices();
          newState.services = availableServices;
          if ( availableServices.length ) {
            availableServices.forEach( function ( service ) {
              MiddlewareClient.getMethods( service );
            });
          }
          break;

        case "methods":
          newState.methods = MiddlewareStore.getAvailableRPCMethods();
          break;
      }

      this.setState( newState );
    }

  , handleRPCErrorCallback: function ( args ) {
      this.setState(
        { anErrorOccurred : true
        , RPCTraceback    : args
        }
      )
    }

  , handleRPCSubmit: function ( value, otherArg ) {
      let val = value;
      // The below is hack to avoid the single-click event's call to
      // handleRPCSubmit to assign a SyntheticMouseEvent to val
      // Fix if possible.
      if ( typeof val === "object" || typeof val === "undefined" ) {
        val = this.state.methodValue
      }
      this.setState({ submissionPending: true });
      try {
        MiddlewareClient.request( val
                                , JSON.parse( this.state.argsValue )
                                , function ( results ) {
            this.setState({ submissionPending : false
                          , results           : results
                          });
          }.bind( this )
                                , this.handleRPCErrorCallback
        );
      }
      catch ( err ) {
        this.handleRPCErrorCallback( freeNASUtil.getStackTrace( err ) );
      }
    }

  , handleMethodClick: function ( rpcString ) {
      this.setState({ methodValue: rpcString });
    }

  , handleMethodDbClick: function ( rpcString ) {
      this.setState({ methodValue: rpcString });
      this.handleRPCSubmit( rpcString );
    }

  , optionSelected: function ( ) {
      this.setState({ methodValue: arguments[0].trim() });
    }

  , handleInputKeyPress: function ( event ) {
      if ( event.which === 13 ) {
        this.handleRPCSubmit();
      }
    }

  , handleArgsInputChange: function ( event ) {
      this.setState({ argsValue: event.target.value });
    }

  , handleResultsChange: function ( event ) {
      this.setState({ results: this.state.results });
    }

  , handleAlertDismiss: function () {
      this.setState(
        { anErrorOccurred   : false
        , submissionPending : false
        })
    }

  , createMethodPanel: function ( service, index ) {
      if ( this.state.methods[ service ] ) {
        var methods = this.state.methods[ service ].map(
          function ( method, index ) {
            var rpcString = service + "." + method["name"];
            return (
              <a key           = { index }
                 className     = "debug-list-item"
                 onClick       = { this.handleMethodClick.bind( null
                                                              , rpcString ) }
                 onDoubleClick = { this.handleMethodDbClick.bind( null
                                                                , rpcString )
                 } >
                { method[ "name" ] }
              </a>
            );
          }.bind( this )
        );

        return (
          <DiscTri headerShow={ service }
                   headerHide={ service }
                   key={ index }
                   defaultExpanded={false}>
            <TWBS.Panel bsStyle="info" key={ index }>
              { methods }
            </TWBS.Panel>
          </DiscTri>
        );

      } else { return null; }
    }

  , render: function () {
      var agmeth = [];
      _.forEach( this.state.methods, function ( value, key ) {
        var svc = key;
        value.map( function ( method, index ) {
          agmeth.push( svc + "." + method["name"] );
        }
        );
      });
      let RPCAlert = "";
      if ( this.state.anErrorOccurred ) {
        let errStack = ( <p> </p> );
        if ( this.state.RPCTraceback.constructor === Array ) {
          errStack = this.state.RPCTraceback.map(
            function ( errval, index ) {
              return ( <p key = { index }>{  errval }</p> )
            }
          );
        } else {
          errStack = ( <p>{this.state.RPCTraceback}</p> );
        }
        RPCAlert = (
          <div className="overlay-error">
            <TWBS.Alert bsStyle='danger' onDismiss={this.handleAlertDismiss}>
              <h4>Oh snap! A very specific Error Occurred</h4>
              {errStack}
              <p>
                <TWBS.Button onClick={this.handleAlertDismiss}>
                 Done
                </TWBS.Button>
              </p>
             </TWBS.Alert>
           </div> )
      }
      return (
        <div className="debug-content-flex-wrapper">
            { RPCAlert }

          <TWBS.Col xs={6} className="debug-column" >

            <h5 className="debug-heading">RPC Interface</h5>
            <TWBS.Row>
              <TWBS.Col xs={5}>
                <FuzzyTypeAhead
                  name="RPC Fuzzy Search"
                  placeholder="Method Name"
                  defaultValue={ this.state.methodValue }
                  options={ agmeth }
                  className="typeahead-list"
                  maxVisible={ 7 }
                  onOptionSelected={ this.optionSelected }
                  onKeyPress={ this.handleInputKeyPress }
                  customClasses={{ input     : "typeahead-text-input"
                                 , results   : "typeahead-list__container"
                                 , listItem  : "typeahead-list__item"
                                 , hover     : "typeahead-active"
                  }} />
              </TWBS.Col>
              <TWBS.Col xs={5}>
              <TWBS.Input
                  type        = "textarea"
                  disabled    = { this.state.submissionPending }
                  style       = {{ resize: "vertical", height: "34px" }}
                  placeholder = "Arguments (JSON Array)"
                  onChange    = { this.handleArgsInputChange }
                  value       = { this.state.argsValue } />
              </TWBS.Col>
              <TWBS.Col xs={2}>
              <TWBS.Button
                    bsStyle  = "primary"
                    disabled = { this.state.submissionPending }
                    onClick  = { this.handleRPCSubmit }
                    block >
                  {"Submit"}
                </TWBS.Button>
              </TWBS.Col>

              <TWBS.Col xs={12}>
                <TWBS.ProgressBar
                  active
                  ref   = "pendingProgressBar"
                  style = {{ display: "none"
                           , opacity: 0
                           , height: "10px"
                           , margin: "0 0 6px 0" }}
                  now   = { 100 } />
              </TWBS.Col>

            </TWBS.Row>

            <h5 className="debug-heading">RPC Results</h5>
            <textarea className = "form-control debug-column-content debug-monospace-content"
                      value     = { JSON.stringify( this.state.results
                                                  , null, 2 ) }
                      style     = {{ resize: "vertical" }}
                      onChange  = { this.handleResultsChange } />

          </TWBS.Col>

          <TWBS.Col xs={6} className="debug-column" >

            <h5 className="debug-heading">Available Service Namespaces</h5>
            <div className="debug-column-content well well-sm">
              { this.state.services.map( this.createMethodPanel ) }
            </div>

          </TWBS.Col>

        </div>
      );
    }

});

module.exports = RPC;
