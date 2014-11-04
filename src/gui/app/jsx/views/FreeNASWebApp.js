/** @jsx React.DOM */

// Main App Wrapper
// ================
// Top level controller-view for FreeNAS webapp
"use strict";


var React  = require("react");

// Page router
var Router = require("react-router");
var Link   = Router.Link;

// Twitter Bootstrap React components
var TWBS   = require("react-bootstrap");

var FreeNASWebApp = React.createClass({
  render: function() {
    return (
      <TWBS.Grid>
        {/* TODO: Add Modal mount div */}
        <TWBS.Row>
          {/* Navigation side menu */}
          <TWBS.Col xs={2} sm={2} md={2} lg={2} xl={2}>
            <ul>
              <li><Link to="storage">Storage</Link></li>
              <li><Link to="users">Users</Link></li>
              <li><Link to="network">Network</Link></li>
              <li><Link to="tasks">Tasks</Link></li>
              <li><Link to="control-panel">Control Panel</Link></li>
            </ul>
          </TWBS.Col>

          {/* Primary view */}
          <TWBS.Col xs={8} sm={8} md={8} lg={8} xl={8}>
            <h1>FreeNAS WebGUI</h1>
            { this.props.activeRouteHandler() }
          </TWBS.Col>

          {/* Tasks and active users */}
          <TWBS.Col xs={2} sm={2} md={2} lg={2} xl={2}>
            {/* TODO: Add tasks/users component */}
          </TWBS.Col>
        </TWBS.Row>
      </TWBS.Grid>
    );
  }
});

module.exports = FreeNASWebApp;