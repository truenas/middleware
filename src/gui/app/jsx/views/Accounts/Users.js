/** @jsx React.DOM */

// Users
// =====
// Viewer for FreeNAS user accounts and built-in system users.

"use strict";

var React = require("react");

var Viewer = require("../../components/Viewer");

var UsersMiddleware = require("../../middleware/UsersMiddleware");
var UsersStore      = require("../../stores/UsersStore");

var viewData = {
    format  : require("../../../data/middleware-keys/accounts-display.json")[0]
  , routing : {
      "route" : "users-editor"
    , "param" : "userID"
  }
  , display : {
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
    , defaultCollapsed : [ ]
  }
};


function getUsersStoreData() {
  return {
      usersList  : UsersStore.getAllUsers()
  };
}


var Users = React.createClass({

    getInitialState: function() {
      return getUsersStoreData();
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
      this.setState( getUsersStoreData() );
    }

  , render: function() {
      return <Viewer header    = { "Users" }
                     inputData = { this.state.usersList }
                     viewData  = { viewData }
                     Editor    = { this.props.activeRouteHandler } />;
    }

});

module.exports = Users;
