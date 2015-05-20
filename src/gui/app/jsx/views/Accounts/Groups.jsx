// Groups
// ======
// Viewer for FreeNAS groups.

"use strict";

var componentLongName = "Groups";

import React from "react";

import Viewer from "../../components/Viewer";

import GroupsMiddleware from "../../middleware/GroupsMiddleware";
import GroupsStore from "../../stores/GroupsStore";

import UsersMiddleware from "../../middleware/UsersMiddleware";
import UsersStore from "../../stores/UsersStore";

var viewData = {
    format    : require("../../../data/middleware-keys/groups-display.json")[0]
  , addEntity : "Add Group"
  , routing   : {
      "route"     : "groups-editor"
    , "param"     : "groupID"
    , "addentity" : "add-group"
  }
  , display   : {
      filterCriteria   : {
        userCreated : {
            name     : "local groups"
          , testProp : { "builtin": false }
        }
      , builtIn     : {
            name     : "built-in system groups"
          , testProp : { "builtin": true }
        }
      }
    , remainingName    : "other groups"
    , ungroupedName    : "all other groups"
    , allowedFilters   : [ ]
    , defaultFilters   : [ ]
    , allowedGroups    : [ "userCreated", "builtIn" ]
    , defaultGroups    : [ "userCreated", "builtIn" ]
    , defaultCollapsed : [ ] // TODO: Revert this to "builtin" once we have more "userCreated"
  }
};

function getGroupsFromStore() {
  return {
    groupsList : GroupsStore.getAllGroups()
  };
}

function getUsersStoreData() {
  return {
      usersList  : UsersStore.getAllUsers()
  };
}

const Groups = React.createClass({

    getInitialState: function () {
      return getGroupsFromStore();
    }

  , componentDidMount: function () {
      GroupsStore.addChangeListener( this.handleGroupsChange );
      GroupsMiddleware.requestGroupsList();
      GroupsMiddleware.subscribe( componentLongName );

      UsersStore.addChangeListener( this.handleUsersChange );
      UsersMiddleware.requestUsersList();
      UsersMiddleware.subscribe( componentLongName );
    }

  , componentWillUnmount: function () {
      GroupsStore.removeChangeListener( this.handleGroupsChange );
      GroupsMiddleware.unsubscribe( componentLongName );

      UsersStore.removeChangeListener( this.handleUsersChange );
      UsersMiddleware.unsubscribe( componentLongName );
    }

  , handleGroupsChange: function () {
      this.setState( getGroupsFromStore() );
    }

  , handleUsersChange: function () {
      this.setState( getUsersStoreData() );
    }

  , render: function () {
      return <Viewer header     = { "Groups" }
                     inputData  = { this.state.groupsList }
                     viewData   = { viewData } />;
    }
});

export default Groups;
