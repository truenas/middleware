// RPC Debug Tab
// =============

"use strict";

var _     = require("lodash");
var React = require("react");
var TWBS  = require("react-bootstrap");

// Middleware
var MiddlewareClient = require("../../middleware/MiddlewareClient");

var RPC = React.createClass({

    getDefaultProps: function() {
      return {
          services : []
        , methods  : {}
      };
    }

  , getInitialState: function() {
      return {
          results     : []
        , methodValue : ""
        , argsValue   : "[]"
      };
    }

  , handleRPCSubmit: function() {
      MiddlewareClient.request( this.state.methodValue, JSON.parse( this.state.argsValue ), function( results ) {
        this.setState({
            results : results
        });
      }.bind(this) );
    }

  , handleMethodClick: function( rpcString ) {
      this.setState({
          methodValue : rpcString
      });
    }

  , handleMethodInputChange: function( event ) {
      this.setState({
          methodValue : event.target.value
      });
    }

  , handleArgsInputChange: function( event ) {
      this.setState({
          argsValue : event.target.value
      });
    }

  , createMethodPanel: function( service, index ) {
    if ( this.props.methods[ service ] ) {
        var methods = this.props.methods[ service ].map(
          function( method, index ) {
            var rpcString = service + "." + method["name"];
            return (
              <TWBS.ListGroupItem key     = { index }
                                  onClick = { this.handleMethodClick.bind( null, rpcString ) } >
                { method["name"] }
              </TWBS.ListGroupItem>
            );
          }.bind(this)
        );

        return (
          <TWBS.Panel bsStyle="info" header={ service } key={ index }>
            <TWBS.ListGroup>
              { methods }
            </TWBS.ListGroup>
          </TWBS.Panel>
        );
    } else {
      return null;
    }
  }

  , render: function() {
      return (
        <div className="debug-content-flex-wrapper">

          <TWBS.Col xs={6} className="debug-column" >

            <h5>RPC Interface</h5>
            <TWBS.Row>
              <TWBS.Col xs={5}>
                <TWBS.Input type        = "text"
                            placeholder = "Method name"
                            onChange    = { this.handleMethodInputChange }
                            value       = { this.state.methodValue } />
              </TWBS.Col>
              <TWBS.Col xs={5}>
                <TWBS.Input type        = "textarea"
                            style       = {{ resize: "vertical" }}
                            placeholder = "Arguments (JSON Array)"
                            onChange    = { this.handleArgsInputChange }
                            value       = { this.state.argsValue } />
              </TWBS.Col>
              <TWBS.Col xs={2}>
                <TWBS.Button bsStyle = "primary"
                             onClick = { this.handleRPCSubmit }
                             block>
                  {"Submit"}
                </TWBS.Button>
              </TWBS.Col>
            </TWBS.Row>

            <h5>Available Service Namespaces</h5>
            <div className="debug-column-content well well-sm">
              { this.props.services.map( this.createMethodPanel ) }
            </div>

          </TWBS.Col>

          <TWBS.Col xs={6} className="debug-column" >

            <h5>RPC Results</h5>
            <pre className="debug-column-content">
              { JSON.stringify( this.state.results, null, 2 ) }
            </pre>

          </TWBS.Col>

        </div>
      );
    }

});

module.exports = RPC;