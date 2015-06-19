// Users
// =====
// Viewer for FreeNAS user accounts and built-in system users.

"use strict";

var componentLongName = "Users";

import React from "react";

import Viewer from "../../components/Viewer";

import UM from "../../middleware/UsersMiddleware";
import US from "../../stores/UsersStore";

import GM from "../../middleware/GroupsMiddleware";
import GS from "../../stores/GroupsStore";

import SS from "../../stores/SessionStore";

function testCurrentUser ( user ) {
  return user.username === SS.getCurrentUser();
}

const VIEWER_DATA =
  { keyUnique     : US.uniqueKey
  , keyPrimary    : "username"
  , keySecondary  : "full_name"

  , itemSchema    : US.itemSchema
  , itemLabels    : US.itemLabels

  , routeName     : "users-editor"
  , routeParam    : "userID"
  , routeAdd      : "add-user"

  , textNewItem   : "Add User"
  , textRemaining : "other user accounts"
  , textUngrouped : "all user accounts"

  , groupsInitial : new Set( [ "current", "userCreated", "builtIn" ] )
  , groupsAllowed : new Set( [ "userCreated", "builtIn" ] )

  , filtersInitial : new Set( )
  , filtersAllowed : new Set( [ "builtIn" ] )

  , columnsInitial : new Set(
                      [ "id"
                      , "builtIn"
                      , "username"
                      , "fullname"
                      ]
                    )
  , columnsAllowed : new Set(
                      [ "id"
                      , "builtIn"
                      , "username"
                      , "fullname"
                      ]
                    )

  , groupBy:
    { current:
       { name: "current user account"
       , testProp: testCurrentUser
       }
    , userCreated:
       { name: "local user accounts"
       , testProp: { builtin: false }
       }
    , builtIn:
       { name: "built-in system accounts"
       , testProp: { builtin: true }
       }
    }
  };

function getUsersStoreData () {
  return { usersList: US.users };
}

function getGroupsFromStore () {
  return { groupsList: GS.getAllGroups() };
}

const Users = React.createClass(

  { getInitialState: function () {
      return getUsersStoreData();
    }

  , componentDidMount: function () {
      US.addChangeListener( this.handleUsersChange );
      UM.requestUsersList();
      UM.subscribe( componentLongName );

      GS.addChangeListener( this.handleGroupsChange );
      GM.requestGroupsList();
      GM.subscribe( componentLongName );
    }

  , componentWillUnmount: function () {
      US.removeChangeListener( this.handleUsersChange );
      UM.unsubscribe( componentLongName );

      GS.removeChangeListener( this.handleGroupsChange );
      GM.unsubscribe( componentLongName );
    }

  , handleGroupsChange: function () {
      this.setState( getGroupsFromStore() );
    }

  , handleUsersChange: function () {
      this.setState( getUsersStoreData() );
    }

  , render: function () {
      return <Viewer
                header   = { "Users" }
                itemData = { this.state.usersList }
                { ...VIEWER_DATA } />;
    }

});

export default Users;
