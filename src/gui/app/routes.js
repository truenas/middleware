/** @jsx React.DOM */

// FREENAS GUI ROUTES
"use strict";

var React        = require("react");

// Routing
var Router        = require("react-router");
var Routes        = Router.Routes;
var Route         = Router.Route;
var Redirect      = Router.Redirect;
var DefaultRoute  = Router.DefaultRoute;
var NotFoundRoute = Router.NotFoundRoute;

// STATIC ROUTES
var Root = require("./jsx/views/FreeNASWebApp");
  var Dashboard    = require("./jsx/views/Dashboard");
  var Accounts     = require("./jsx/views/Accounts");
    var Users  = require("./jsx/views/Accounts/Users");
    var Groups = require("./jsx/views/Accounts/Groups");
  var Tasks        = require("./jsx/views/Tasks");
  var Network      = require("./jsx/views/Network");
  var Storage      = require("./jsx/views/Storage");
  var Sharing      = require("./jsx/views/Sharing");
  var Services     = require("./jsx/views/Services");
  var SystemTools  = require("./jsx/views/SystemTools");
  var ControlPanel = require("./jsx/views/ControlPanel");
  var Power        = require("./jsx/views/Power");

var PageNotFound = require("./jsx/views/PageNotFound");

var Editor = require("./jsx/components/Viewer/Editor");

module.exports = (
  <Routes location="history">
    <Route path="/" handler={ Root }>
      <DefaultRoute handler={ Dashboard } />
      <Route name="dashboard" handler={ Dashboard } />

      {/* ACCOUNTS */}
      <Route name="accounts" handler={ Accounts }>
        <DefaultRoute handler={ Users } />
        <Route name    = "users"
               path    = "/accounts/users"
               handler = { Users } >
          <Route name    = "users-editor"
                 path    = "/accounts/users/:userID"
                 handler = { Editor } />
        </Route>
        <Route name    = "groups"
               path    = "/accounts/groups"
               handler = { Groups } >
          <Route name    = "groups-editor"
                 path    = "/accounts/groups/:groupID"
                 handler = { Editor } />
        </Route>
      </Route>

      <Route name="tasks" handler={ Tasks } />
      <Route name="network" handler={ Network } />
      <Route name="storage" handler={ Storage } />
      <Route name="sharing" handler={ Sharing } />

      <Route name="services" handler={ Services }>
        <Route name    = "services-editor"
               path    = "/services/:serviceID"
               handler = { Editor } />
      </Route>

      <Route name="system-tools" handler={ SystemTools } />
      <Route name="control-panel" handler={ ControlPanel } />
      <Route name="power" handler={ Power } />
    </Route>
    <NotFoundRoute handler={ PageNotFound } />
  </Routes>
);