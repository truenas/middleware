// Groups
// ======
// Viewer for FreeNAS groups.

"use strict";

const componentLongName = "Groups";

import React from "react";

import Viewer from "../../components/Viewer";

import GM from "../../middleware/GroupsMiddleware";
import GS from "../../stores/GroupsStore";

import UM from "../../middleware/UsersMiddleware";
import US from "../../stores/UsersStore";

const VIEWER_DATA =
  { keyUnique     : GS.uniqueKey
  , keyPrimary    : "groupName"
  , keySecondary  : "groupID"

  , itemSchema    : GS.itemSchema
  , itemLabels    : GS.itemLabels

  , routeName     : "groups-editor"
  , routeParam    : "groupID"
  , routeAdd      : "add-group"

  , textNewItem   : "Add Group"
  , textRemaining : "other groups"
  , textUngrouped : "all groups"

  , groupsInitial : new Set( [ "userCreated", "builtIn" ] )
  , groupsAllowed : new Set( [ "userCreated", "builtIn" ] )

  , filtersInitial : new Set( )
  , filtersAllowed : new Set( [ "builtIn" ] )

  , columnsInitial : new Set(
                      [ "groupID"
                      , "groupName"
                      , "builtIn"
                      ]
                    )
  , columnsAllowed : new Set(
                      [ "groupID"
                      , "groupName"
                      , "builtIn"
                      ]
                    )

  , groupBy:
    { userCreated:
       { name: "local groups"
       , testProp: { builtIn: false }
       }
    , builtIn:
       { name: "built-in system groups"
       , testProp: { builtIn: true }
       }
    }
  };

function getGroupsFromStore () {
  return {
    groupsList: GS.groups
  };
}

function getUsersStoreData () {
  return {
    usersList: US.users
  };
}

const Groups = React.createClass({

  getInitialState: function () {
    return getGroupsFromStore();
  }

  , componentDidMount: function () {
    GS.addChangeListener( this.handleGroupsChange );
    GM.requestGroupsList();
    GM.subscribe( componentLongName );

    US.addChangeListener( this.handleUsersChange );
    UM.requestUsersList();
    UM.subscribe( componentLongName );
  }

  , componentWillUnmount: function () {
    GS.removeChangeListener( this.handleGroupsChange );
    GM.unsubscribe( componentLongName );

    US.removeChangeListener( this.handleUsersChange );
    UM.unsubscribe( componentLongName );
  }

  , handleGroupsChange: function () {
    this.setState( getGroupsFromStore() );
  }

  , handleUsersChange: function () {
    this.setState( getUsersStoreData() );
  }

  , render: function () {
    return <Viewer
             header = { "Groups" }
             itemData = { this.state.groupsList }
             { ...VIEWER_DATA } />;
  }
});

export default Groups;
