// FREENAS GUI ROUTES
// ==================

"use strict";

var React = require("react");

// Routing
var Router        = require("react-router");
var Route         = Router.Route;
var DefaultRoute  = Router.DefaultRoute;
var NotFoundRoute = Router.NotFoundRoute;

// STATIC ROUTES
var Root = require("./views/FreeNASWebApp");
  var Dashboard    = require("./views/Dashboard");

  var Accounts     = require("./views/Accounts");
    var Users      = require("./views/Accounts/Users");
      var UserItem = require("./views/Accounts/Users/UserItem");

    var Groups     = require("./views/Accounts/Groups");

  var Tasks        = require("./views/Tasks");

  var Networks      = require("./views/Networks");
    var NetworkItem = require("./views/Networks/NetworkItem");

  var Storage      = require("./views/Storage");
  var Sharing      = require("./views/Sharing");
  var Services     = require("./views/Services");
  var SystemTools  = require("./views/SystemTools");
  var ControlPanel = require("./views/ControlPanel");
  var Power        = require("./views/Power");

var PageNotFound = require("./views/PageNotFound");

var Editor = require("./components/Viewer/Editor");

module.exports = (
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
               handler = { UserItem } />
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

      <Route name    = "networks"
             path    = "networks"
             handler = { Networks } >
        <Route name    = "networks-editor"
               path    = "/networks/:networksID"
               handler = { NetworkItem } />
      </Route>

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
    <NotFoundRoute handler={ PageNotFound } />
  </Route>
);
