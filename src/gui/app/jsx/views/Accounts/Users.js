/** @jsx React.DOM */

// Users
// =====
// Viewer for FreeNAS user accounts and built-in system users.

"use strict";

var _     = require("lodash");
var React = require("react");

var Viewer   = require("../../components/Viewer");
var UserView = require("./Users/UserView");
var UserEdit = require("./Users/UserEdit");

var UsersMiddleware = require("../../middleware/UsersMiddleware");
var UsersStore      = require("../../stores/UsersStore");

var formatData = require("../../../data/middleware-keys/accounts-display.json")[0];
var itemData = {
    "route" : "users-editor"
  , "param" : "userID"
};

var displaySettings = {
    filterCriteria: {
        current: {
            name     : "current user account"
          // TODO: Fix dummy data
          , testProp : { "username": "jakub" }
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
  , defaultCollapsed : [ "builtIn" ]
};


function getUsersFromStore() {
  return {
    usersList: UsersStore.getAllUsers()
  };
}


var Users = React.createClass({

    getInitialState: function() {
      return getUsersFromStore();
    }

  , componentDidMount: function() {
      UsersStore.addChangeListener( this.handleUsersChange );
      UsersMiddleware.requestUsersList();
      UsersMiddleware.subscribe();

    }

  , componentWillUnmount: function() {
      UsersStore.removeChangeListener( this.handleUsersChange );
      UsersMiddleware.unsubscribe();
    }

  , handleUsersChange: function() {
      this.setState( getUsersFromStore() );
    }

  , render: function() {
      return (
        <Viewer header      = { "Users" }
                inputData   = { this.state.usersList }
                displayData = { displaySettings }
                formatData  = { formatData }
                itemData    = { itemData }
                ItemView    = { UserView }
                EditView    = { UserEdit }
                Editor      = { this.props.activeRouteHandler }>
        </Viewer>
      );
    }

});

module.exports = Users;
