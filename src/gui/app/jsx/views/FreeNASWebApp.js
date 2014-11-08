/** @jsx React.DOM */

// Main App Wrapper
// ================
// Top level controller-view for FreeNAS webapp
"use strict";


var React  = require("react");

// Page router
var Router = require("react-router");
var Link   = Router.Link;

var Icon   = require("../components/Icon");
// Twitter Bootstrap React components
var TWBS   = require("react-bootstrap");

var FreeNASWebApp = React.createClass({
  render: function() {
    return (
      <div>
      <div className="notificationBar">Notification Bar will live here!</div>
      <div className="leftMenu">
        <div className="leftMenuContent">
                <ul>
                  <li><Icon glyph="dashboard" /><Link to="dashboard">Dashboard</Link></li>
                  <li><Icon glyph="accounts" /><Link to="accounts">Accounts</Link></li>
                  <li><Icon glyph="tasks" /><Link to="tasks">Tasks</Link></li>          
                  <li><Icon glyph="network" /><Link to="network">Network</Link></li>
                  <li><Icon glyph="storage" /><Link to="storage">Storage</Link></li>
                  <li><Icon glyph="sharing" /><Link to="sharing">Sharing</Link></li>                    
                  <li><Icon glyph="services" /><Link to="services">Services</Link></li>          
                  <li><Icon glyph="system-tools" /><Link to="system-tools">System Tools</Link></li>
                  <li><Icon glyph="control-panel" /><Link to="control-panel">Control Panel</Link></li>
                  <li><Icon glyph="power" /><Link to="power">Power</Link></li>
                </ul>
        </div>
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