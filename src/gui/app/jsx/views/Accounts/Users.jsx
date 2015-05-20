// Users
// =====
// Viewer for FreeNAS user accounts and built-in system users.

"use strict";

var componentLongName = "Users";

import React from "react";

import Viewer from "../../components/Viewer";

import UsersMiddleware from "../../middleware/UsersMiddleware";
import UsersStore from "../../stores/UsersStore";

import GroupsMiddleware from "../../middleware/GroupsMiddleware";
import GroupsStore from "../../stores/GroupsStore";

import SessionStore from "../../stores/SessionStore";

var viewData = {
    format    : require("../../../data/middleware-keys/users-display.json")[0]
  , addEntity : "Add User"
  , routing   : {
      "route"      : "users-editor"
    , "param"      : "userID"
    , "addentity"  : "add-user"
  }
  , display   : {
      filterCriteria: {
          current: {
              name     : "current user account"
            , testProp : function(user){ return user.username === SessionStore.getCurrentUser(); }
          }
        , userCreated: {
              name     : "local user accounts"
            , testProp : { "builtin": false }
          }
        , builtIn: {
              name     : "built-in system accounts"
            , testProp : { "builtin": true }
          }
      }
    , remainingName    : "other user accounts"
    , ungroupedName    : "all user accounts"
    , allowedFilters   : [ ]
    , defaultFilters   : [ ]
    , allowedGroups    : [ "current", "userCreated", "builtIn" ]
    , defaultGroups    : [ "current", "userCreated", "builtIn" ]
    , defaultCollapsed : [ ]
  }
};

function getUsersStoreData() {
  return {
      usersList  : UsersStore.getAllUsers()
  };
}

function getGroupsFromStore() {
  return {
    groupsList : GroupsStore.getAllGroups()
  };
}

const Users = React.createClass({

    getInitialState: function () {
      return getUsersStoreData();
    }

  , componentDidMount: function () {
      UsersStore.addChangeListener( this.handleUsersChange );
      UsersMiddleware.requestUsersList();
      UsersMiddleware.subscribe( componentLongName );

      GroupsStore.addChangeListener( this.handleGroupsChange );
      GroupsMiddleware.requestGroupsList();
      GroupsMiddleware.subscribe( componentLongName );
    }

  , componentWillUnmount: function () {
      UsersStore.removeChangeListener( this.handleUsersChange );
      UsersMiddleware.unsubscribe( componentLongName );

      GroupsStore.removeChangeListener( this.handleGroupsChange );
      GroupsMiddleware.unsubscribe( componentLongName );
    }

  , handleGroupsChange: function () {
      this.setState( getGroupsFromStore() );
    }

  , handleUsersChange: function () {
      this.setState( getUsersStoreData() );
    }

  , render: function () {
      return <Viewer
                header    = { "Users" }
                inputData = { this.state.usersList }
                viewData  = { viewData } />;
    }

});

export default Users;
