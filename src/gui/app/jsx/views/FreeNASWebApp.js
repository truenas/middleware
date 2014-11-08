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
      <div>
      <div className="notificationBar">Notification Bar will live here!</div>
      <div className="leftMenu">
        <ul>
          <li><Link to="dashboard" className="ico-dashboard">Dashboard</Link></li>
          <li><Link to="accounts" className="ico-accounts ">Accounts</Link></li>
          <li><Link to="tasks" className="ico-tasks ">Tasks</Link></li>
          <li><Link to="network" className="ico-network ">Network</Link></li>
          <li><Link to="storage" className="ico-storage ">Storage</Link></li>
          <li><Link to="sharing" className="ico-sharing ">Sharing</Link></li>
          <li><Link to="services" className="ico-services">Services</Link></li>
          <li><Link to="system-tools" className="ico-system-tools ">System Tools</Link></li>
          <li><Link to="control-panel" className="ico-control-panel">Control Panel</Link></li>
          <li><Link to="power" className="ico-power ">Power</Link></li>
        </ul>
      </div>
      <TWBS.Grid fluid className="mainGrid">
        {/* TODO: Add Modal mount div */}
        <TWBS.Row>
          {/* Primary view */}
          <TWBS.Col xs={9} sm={9} md={9} lg={9} xl={9}
                    xsOffset={1} smOffset={1} mdOffset={1} lgOffset={1} xlOffset={1}>
            <h1>FreeNAS WebGUI</h1>
            { this.props.activeRouteHandler() }
          </TWBS.Col>

          {/* Tasks and active users */}
          <TWBS.Col xs={2} sm={2} md={2} lg={2} xl={2}>
            {/* TODO: Add tasks/users component */}
          </TWBS.Col>
        </TWBS.Row>
      </TWBS.Grid>
      </div>
    );
  }
});

module.exports = FreeNASWebApp;