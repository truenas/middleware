// Main App Wrapper
// ================
// Top level controller-view for FreeNAS webapp
"use strict";

var React = require("react");

var Router       = require("react-router");
var RouteHandler = Router.RouteHandler;

var routerShim = require("../components/mixins/routerShim");

// WebApp Components
var BusyBox           = require("../components/BusyBox");
var NotificationBar   = require("../components/WebApp/NotificationBar");
var InformationBar    = require("../components/WebApp/InformationBar");
var PrimaryNavigation = require("../components/PrimaryNavigation");
var DebugTools        = require("../components/DebugTools");


var FreeNASWebApp = React.createClass({

    mixins: [ routerShim ]

  , componentDidMount: function() {
      this.calculateDefaultRoute( "/", "dashboard", "is" );
    }

  , componentDidUpdate: function( prevProps, prevState ) {
      this.calculateDefaultRoute( "/", "dashboard", "is" );
    }

  , render: function() {

      return (
        <div className="app-wrapper">
          {/* TODO: Add Modal mount div */}

          {/* Modal windows for busy spinner and/or FreeNAS login
                -- hidden normally except when invoked*/}
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
