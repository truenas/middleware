/** @jsx React.DOM */

// Main App Wrapper
// ================
// Top level controller-view for FreeNAS webapp
"use strict";

var _     = require("lodash");
var React = require("react");

// Middleware
var MiddlewareClient = require("../middleware/MiddlewareClient");
var MiddlewareStore  = require("../stores/MiddlewareStore");

// Twitter Bootstrap React components
var TWBS = require("react-bootstrap");

// WebApp Components
var LoginBox          = require("../components/LoginBox");
var NotificationBar   = require("../components/WebApp/NotificationBar");
var InformationBar    = require("../components/WebApp/InformationBar");
var PrimaryNavigation = require("../components/PrimaryNavigation");


// Middleware Utilies
function getMiddlewareStateFromStores () {
  return {
      authenticated : MiddlewareStore.getAuthStatus()
  };
}


var FreeNASWebApp = React.createClass({

    getInitialState: function () {
      return _.assign( { /* Non-Flux state goes here */ },
                       getMiddlewareStateFromStores() );
    }

  , componentDidMount: function () {
      MiddlewareStore.addChangeListener( this.handleMiddlewareChange );
    }

  , handleMiddlewareChange: function () {
      this.setState( getMiddlewareStateFromStores() );
  }

  , render: function() {

    return (
      <div className="app-wrapper">
        {/* TODO: Add Modal mount div */}

        {/* Modal window for FreeNAS login - hidden when authenticated */}
        <LoginBox isHidden={ this.state.authenticated } />

        {/* Header containing system status and information */}
        <NotificationBar />

        {/* Primary navigation menu */}
        <PrimaryNavigation />

        {/* Primary view */}
        <this.props.activeRouteHandler />

        {/* User-customizable component showing system events */}
        <InformationBar />

        <footer className="app-footer">
        </footer>
      </div>
    );
  }
});

module.exports = FreeNASWebApp;