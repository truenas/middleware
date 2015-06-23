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
import UserAdd from "./views/Accounts/Users/UserAdd";

import Groups from "./views/Accounts/Groups";
import GroupItem from "./views/Accounts/Groups/GroupItem";
import AddGroup from "./views/Accounts/Groups/AddGroup";

import Tasks from "./views/Tasks";

import Network from "./views/Network";
import NetworkOverview from "./views/Network/NetworkOverview";
import Interfaces from "./views/Network/Interfaces"
import InterfaceItem from "./views/Network/Interfaces/InterfaceItem";
import NetworkSettings from "./views/Network/NetworkSettings";

import Storage from "./views/Storage";
import Disks from "./views/Storage/Disks";
import DiskItem from "./views/Storage/Disks/DiskItem";

import Services from "./views/Services";
import ServiceItem from "./views/Services/ServiceItem";

import System from "./views/System";
import Update from "./views/System/Update";
import Power from "./views/System/Power";

import Settings from "./views/Settings";

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
          handler = { UserAdd } />
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
      name    = "network"
      path    = "network"
      handler = { Network } >

      {/* GLOBAL NETWORK OVERVIEW */}
      <Route
        name    = "overview"
        path    = "overview"
        handler = { NetworkOverview } />

      {/* NETWORK INTERFACES */}
      <Route
        name    = "interfaces"
        path    = "interfaces"
        handler = { Interfaces } >
        <Route
          name    = "interfaces-editor"
          path    = ":interfaceName"
          handler = { InterfaceItem } />
      </Route>

      {/* NETWORK SETTINGS */}
      <Route
        name    = "network-settings"
        path    = "settings"
        handler = { NetworkSettings } />

    </Route>


    {/* STORAGE */}
    <Route
      name    = "storage"
      route   = "storage"
      handler = { Storage } >
      <Route
        name    = "disk-item-view"
        path    = "disks/:diskSerial"
        handler = { DiskItem }
      />
    </Route>


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


    {/* SYSTEM */}
    <Route
      name    = "system"
      route   = "system"
      handler = { System }>
      <DefaultRoute handler={ Update } />
      <Route
        name    = "update"
        path   = "update"
        handler = { Update } />
      <Route
        name    = "power"
        path   = "power"
        handler = { Power } />
    </Route>

    {/* SETTINGS */}
    <Route
      name    = "settings"
      route   = "settings"
      handler = { Settings } />

    <NotFoundRoute handler={ Dashboard } />

  </Route>
);
