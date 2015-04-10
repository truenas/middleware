// FREENAS GUI ROUTES
// ==================

"use strict";

var React = require("react");

// Routing
var Router        = require("react-router");
var Route         = Router.Route;
var Redirect      = Router.Redirect;
var DefaultRoute  = Router.DefaultRoute;
var NotFoundRoute = Router.NotFoundRoute;

// STATIC ROUTES
var Root = require("./views/FreeNASWebApp");
  var Dashboard    = require("./views/Dashboard");

  var Accounts     = require("./views/Accounts");
    var Users      = require("./views/Accounts/Users");
      var UserItem = require("./views/Accounts/Users/UserItem");
      var AddUser  = require("./views/Accounts/Users/AddUser");

    var Groups       = require("./views/Accounts/Groups");
      var GroupItem = require("./views/Accounts/Groups/GroupItem");
      var AddGroup  = require("./views/Accounts/Groups/AddGroup");

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
    <Route
        name    = "dashboard"
        route   = "dashboard"
        handler = { Dashboard } />

    {/* ACCOUNTS */}
    <Route
        name    = "accounts"
        path    = "accounts"
        handler = { Accounts }>
      <DefaultRoute handler={ Users } />

      {/* USERS */}
      <Route
          name    = "users"
          path    = "users"
          handler = { Users } >
        <Route
            name    = "add-user"
            path    = "add-user"
            handler = { AddUser } />
        <Route
          name    = "users-editor"
          path    = ":userID"
          handler = { UserItem } />
      </Route>

      {/* GROUPS */}
      <Route
          name    = "groups"
          path    = "groups"
          handler = { Groups } >
        <Route
            name    = "add-group"
            path    = "add-group"
            handler = { AddGroup } />
        <Route
            name    = "groups-editor"
            path    = ":groupID"
            handler = { GroupItem } />
      </Route>
    </Route>

    {/* TASKS */}
    <Route
        name    = "tasks"
        route   = "tasks"
        handler = { Tasks } />


    {/* NETWORKS */}
    <Route name    = "networks"
           path    = "networks"
           handler = { Networks } >
      <Route name    = "networks-editor"
             path    = ":networksID"
             handler = { NetworkItem } />
    </Route>


    {/* STORAGE */}
    <Route
        name    = "storage"
        route   = "storage"
        handler = { Storage } />

    {/* SHARING */}
    <Route
        name    = "sharing"
        route   = "sharing"
        handler = { Sharing } />


    {/* SERVICES */}
    <Route
        name    = "services"
        route   = "services"
        handler = { Services }>
      <Route name    = "services-editor"
             path    = ":serviceID"
             handler = { Editor } />
    </Route>


    {/* SYSTEM TOOLS */}
    <Route
        name    = "system-tools"
        route   = "system-tools"
        handler = { SystemTools } />

    {/* CONTROL PANEL */}
    <Route
        name    = "control-panel"
        route   = "control-panel"
        handler = { ControlPanel } />

    {/* POWER */}
    <Route
        name    = "power"
        route   = "power"
        handler = { Power } />

    <NotFoundRoute handler={ Dashboard } />

  </Route>
);
