// Groups
// ======
// Viewer for FreeNAS groups.

"use strict";

var componentLongName = "Groups";

import React from "react";

import Viewer from "../../components/Viewer";

var viewData = {
  addEntity : "Add Group"
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
import GM from "../../middleware/GroupsMiddleware";
import GS from "../../stores/GroupsStore";

import UM from "../../middleware/UsersMiddleware";
import US from "../../stores/UsersStore";


function getGroupsFromStore () {
  return {
    groupsList : GS.groups
  };
}

function getUsersStoreData () {
  return {
    usersList  : US.users
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
      return <Viewer header     = { "Groups" }
                     inputData  = { this.state.groupsList }
                     viewData   = { viewData } />;
    }
});

export default Groups;
