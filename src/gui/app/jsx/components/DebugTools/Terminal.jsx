// Terminal Tab
// ============

"use strict";

var React = require("react");
var TWBS  = require("react-bootstrap");

var ShellMiddleware = require("../../middleware/ShellMiddleware");

var Shell = require("../common/Shell");

var Terminal = React.createClass({

  getInitialState: function() {
    return {
      currentShell: "/bin/sh"
    };
  },

  componentDidMount: function() {
      ShellMiddleware.requestAvailableShells( function( shells ) {
        this.setState({ shells: shells });
      }.bind( this ) );
  },

  render: function() {
    return (
      <div className="debug-content-flex-wrapper">

        <TWBS.Col xs={6} className="debug-column" >

          <h5 className="debug-heading">{"FreeNAS Shell: " + this.state.currentShell }</h5>
          <Shell />

        </TWBS.Col>

        <TWBS.Col xs={6} className="debug-column" >



        </TWBS.Col>
      </div>
    );
  }
});

module.exports = Terminal;
