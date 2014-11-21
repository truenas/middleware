/** @jsx React.DOM */

// Users
// =====
// Viewer for FreeNAS user accounts and built-in system users.

"use strict";


var React    = require("react");

var Viewer   = require("../../components/Viewer");
var UserView = require("./Users/UserView");

var UsersMiddleware = require("../../middleware/UsersMiddleware");
var UsersStore      = require("../../stores/UsersStore");


// Dummy data from API call on relatively unmolested system
// TODO: Update to use data from Flux store
// var inputData  = require("../../../data/fakedata/accounts.json");
var formatData = require("../../../data/middleware-keys/accounts-display.json")[0];
var itemData = {
    "route" : "users-editor"
  , "param" : "userID"
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
        <Viewer header     = { "Users" }
                inputData  = { this.state.usersList }
                formatData = { formatData }
                itemData   = { itemData }
                ItemView   = { UserView }
                Editor     = { this.props.activeRouteHandler }>
        </Viewer>
      );
    }

});

module.exports = Users;
