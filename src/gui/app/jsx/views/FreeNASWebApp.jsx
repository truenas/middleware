// Main App Wrapper
// ================
// Top level controller-view for FreeNAS webapp
"use strict";

var React = require("react");

var Router       = require("react-router");
var RouteHandler = Router.RouteHandler;

// WebApp Components
var LoginBox          = require("../components/LoginBox");
var BusyBox           = require("../components/BusyBox");
var NotificationBar   = require("../components/WebApp/NotificationBar");
var InformationBar    = require("../components/WebApp/InformationBar");
var PrimaryNavigation = require("../components/PrimaryNavigation");
var DebugTools        = require("../components/DebugTools");


var FreeNASWebApp = React.createClass({render: function() {

    return (
      <div className="app-wrapper">
        {/* TODO: Add Modal mount div */}

        {/* Modal window for FreeNAS login - hidden when authenticated */}
        <LoginBox />

        {/* Modal windows for busy spinner -- hidden normally except when invoked*/}
        <BusyBox />

        {/* Header containing system status and information */}
        <NotificationBar />

        <div className="app-content">
          {/* Primary navigation menu */}
          <PrimaryNavigation />

          {/* Primary view */}
          <RouteHandler />

          {/* User-customizable component showing system events */}
          <InformationBar />
        </div>

        <footer className="app-footer">
        </footer>

        <DebugTools />
      </div>
    );
  }
});

module.exports = FreeNASWebApp;