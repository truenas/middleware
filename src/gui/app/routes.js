/** @jsx React.DOM */

// FREENAS GUI ROUTES
"use strict";

// Routing
var Router        = require("react-router");
var Routes        = Router.Routes;
var Route         = Router.Route;
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

module.exports = (
  <Routes location="history">
    <Route path="/" handler={ Root }>
      <DefaultRoute handler={ Dashboard } />
      <Route name="dashboard" handler={ Dashboard } />
      <Route name="accounts" handler={ Accounts }>
        <DefaultRoute handler={ Users } />
        <Route name    = "users"
               path    = "/accounts/users"
               handler = { Users } />
        <Route name    = "groups"
               path    = "/accounts/groups"
               handler = { Groups } />
      </Route>
      <Route name="tasks" handler={ Tasks } />
      <Route name="network" handler={ Network } />
      <Route name="storage" handler={ Storage } />
      <Route name="sharing" handler={ Sharing } />
      <Route name="services" handler={ Services } />
      <Route name="system-tools" handler={ SystemTools } />
      <Route name="control-panel" handler={ ControlPanel } />
      <Route name="power" handler={ Power } />
    </Route>
    <NotFoundRoute handler={ PageNotFound } />
  </Routes>
);