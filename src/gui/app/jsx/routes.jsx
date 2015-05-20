// FREENAS GUI ROUTES
// ==================

"use strict";

import React from "react";

// Routing
import Router from "react-router";
const Route         = Router.Route;
const Redirect      = Router.Redirect;
const DefaultRoute  = Router.DefaultRoute;
const NotFoundRoute = Router.NotFoundRoute;

// STATIC ROUTES
import Root from "./views/FreeNASWebApp";
import PageNotFound from "./views/PageNotFound";

import Dashboard from "./views/Dashboard";

import Accounts from "./views/Accounts";
import Users from "./views/Accounts/Users";
import UserItem from "./views/Accounts/Users/UserItem";
import AddUser from "./views/Accounts/Users/AddUser";

import Groups from "./views/Accounts/Groups";
import GroupItem from "./views/Accounts/Groups/GroupItem";
import AddGroup from "./views/Accounts/Groups/AddGroup";

import Tasks from "./views/Tasks";

import Network from "./views/Network";
import Interfaces from "./views/Network/Interfaces"
import InterfaceItem from "./views/Network/Interfaces/InterfaceItem";
import NetworkConfig from "./views/Network/NetworkConfig";

import Storage from "./views/Storage";
import Disks from "./views/Storage/Disks";

import Sharing from "./views/Sharing";

import Services from "./views/Services";
import ServiceItem from "./views/Services/ServiceItem";

import SystemTools from "./views/SystemTools";

import ControlPanel from "./views/ControlPanel";

import Power from "./views/Power";

module.exports = (
  <Route
    path    = "/"
    handler = { Root } >

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


    {/* NETWORK */}
    <Route
      name = "network"
      path = "network"
      handler = { Network } >

      {/* GLOBAL NETWORK CONFIGURATION */}
      <Route
        name = "network-config"
        path = "network-config"
        handler = { NetworkConfig } />

      {/* NETWORK INTERFACES */}
      <Route
        name = "interfaces"
        path = "interfaces"
        handler = { Interfaces } >
        <Route
          name = "interfaces-editor"
          path = ":interfaceID"
          handler = { InterfaceItem } />
      </Route>

    </Route>


    {/* STORAGE */}
    <Route
      name    = "storage"
      route   = "storage"
      handler = { Storage } >
      <Route
        name    = "disks"
        route   = "disks"
        handler = { Disks } />
    </Route>

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
      <Route
        name    = "services-editor"
        path    = ":serviceID"
        handler = { ServiceItem } />
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
