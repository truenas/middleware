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
      <div className = "notificationBar">
        <div className = "notificationBox">
          <div className = "notificationArea">
          <textarea className = "form-control" rows="10" >Notification Bar will live here!</textarea>
          </div>
          <div className = "notificationIcons">
            <Icon glyph = "camera-retro" icoSize = "2x" icoClass = "circle" />
            <Icon glyph = "paw" icoSize = "2x" icoClass = "circle" />
            <Icon glyph="bitcoin" icoSize="2x" icoClass = "circle" />
            <Icon glyph="moon-o" icoSize="2x" icoClass = "circle" />
            <Icon glyph="ambulance" icoSize="2x" icoClass = "circle" />
            <Icon glyph="plug" icoSize="2x" icoClass = "circle" />
          </div>
        </div>
        <div className="userInfo">
        <Icon glyph="warning" icoClass="icoAlert" icoSize="3x" warningFlag="2" />
        <Icon glyph = "user" icoSize = "3x" />
        <span className="userName"> LaCoVa </span>
        <Icon glyph = "fire-extinguisher" icoSize = "3x" />

        </div>
      </div>
      <div className="leftMenu">
        <div className="leftMenuContent">
                <ul>
                  <li><Link to="dashboard"><Icon glyph="dashboard" icoClass="icoAlert" warningFlag="!" />Dashboard</Link></li>
                  <li><Link to="accounts"><Icon glyph="paper-plane" />Accounts</Link></li>
                  <li><Link to="tasks"><Icon glyph="paw" />Tasks</Link></li>          
                  <li><Link to="network"><Icon glyph="moon-o" />Network</Link></li>
                  <li><Link to="storage"><Icon glyph="magic" />Storage</Link></li>
                  <li><Link to="sharing"><Icon glyph="cut" />Sharing</Link></li>                    
                  <li><Link to="services"><Icon glyph="bitcoin" />Services</Link></li>          
                  <li><Link to="system-tools"><Icon glyph="ambulance" icoClass="icoWarning" warningFlag="!" />System Tools</Link></li>
                  <li><Link to="control-panel"><Icon glyph="paragraph" />Control Panel</Link></li>
                  <li><Link to="power"><Icon glyph="plug" />Power</Link></li>
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