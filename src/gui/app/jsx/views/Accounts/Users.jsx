// Users
// =====
// Viewer for FreeNAS user accounts and built-in system users.

"use strict";

var componentLongName = "Users";

var React = require("react");

var Router       = require("react-router");
var RouteHandler = Router.RouteHandler;

var Viewer = require("../../components/Viewer");

var UsersMiddleware = require("../../middleware/UsersMiddleware");
var UsersStore      = require("../../stores/UsersStore");

var GroupsMiddleware = require("../../middleware/GroupsMiddleware");
var GroupsStore      = require("../../stores/GroupsStore");

var SessionStore   = require("../../stores/SessionStore");

var viewData = {
    format  : require("../../../data/middleware-keys/users-display.json")[0]
  , routing : {
      "route" : "users-editor"
    , "param" : "userID"
  }
  , display : {
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

var Users = React.createClass({

    getInitialState: function() {
      return getUsersStoreData();
    }

  , componentDidMount: function() {
      UsersStore.addChangeListener( this.handleUsersChange );
      UsersMiddleware.requestUsersList();
      UsersMiddleware.subscribe( componentLongName );

      GroupsStore.addChangeListener( this.handleGroupsChange );
      GroupsMiddleware.requestGroupsList();
      GroupsMiddleware.subscribe( componentLongName );
    }

  , componentWillUnmount: function() {
      UsersStore.removeChangeListener( this.handleUsersChange );
      UsersMiddleware.unsubscribe( componentLongName );

      GroupsStore.removeChangeListener( this.handleGroupsChange );
      GroupsMiddleware.unsubscribe( componentLongName );
    }

  , handleGroupsChange: function() {
      this.setState( getGroupsFromStore() );
    }

  , handleUsersChange: function() {
      this.setState( getUsersStoreData() );
    }

  , render: function() {
      return <Viewer header    = { "Users" }
                     inputData = { this.state.usersList }
                     viewData  = { viewData }
                     Editor    = { RouteHandler } />;
    }

});

module.exports = Users;
