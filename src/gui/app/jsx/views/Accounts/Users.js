/** @jsx React.DOM */

// Users
// =====
// Viewer for FreeNAS user accounts and built-in system users.

"use strict";

var _     = require("lodash");
var React = require("react");

var Viewer   = require("../../components/Viewer");
var UserView = require("./Users/UserView");

var UsersMiddleware = require("../../middleware/UsersMiddleware");
var UsersStore      = require("../../stores/UsersStore");


// Dummy data from API call on relatively unmolested system
var formatData = require("../../../data/middleware-keys/accounts-display.json")[0];
var itemData = {
    "route" : "users-editor"
  , "param" : "userID"
};

var displaySettings = {
    filterCriteria: {
        current: {
            name     : "Current User Account"
          , group    : true
          , filter   : true
          // TODO: Fix dummy data
          , testProp : { "username": "root" }
        }
      , userCreated: {
            name     : "FreeNAS User Accounts"
          , group    : true
          , filter   : true
          , testProp : { "builtin": false }
        }
      , builtIn: {
            name     : "Built-In User Accounts"
          , group    : true
          , filter   : true
          , testProp : { "builtin": true }
        }
    }
  , defaultFilters : [ "builtIn" ]
  , defaultGroups  : [ "current", "userCreated", "builtIn" ]
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
      UsersMiddleware.subscribe();
      UsersMiddleware.requestUsersList();

      UsersStore.addChangeListener( this.handleUsersChange );
    }

  , componentWillUnmount: function() {
      UsersMiddleware.unsubscribe();

      UsersStore.removeChangeListener( this.handleUsersChange );
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
                Editor      = { this.props.activeRouteHandler }>
        </Viewer>
      );
    }

});

module.exports = Users;
