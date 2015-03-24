// Groups
// ======
// Viewer for FreeNAS groups.

"use strict";


var React = require("react");

var Router       = require("react-router");
var RouteHandler = Router.RouteHandler;

var Viewer = require("../../components/Viewer");

var GroupsMiddleware = require("../../middleware/GroupsMiddleware");
var GroupsStore = require("../../stores/GroupsStore");


var viewData = {
    format  : require("../../../data/middleware-keys/groups-display.json")[0]
  , routing : {
      "route" : "groups-editor"
    , "param" : "groupID"
  }
  , display : {
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
    , defaultCollapsed : [ "builtIn" ]
  }
};

function getGroupsFromStore() {
  return {
    groupsList : GroupsStore.getAllGroups()
  };
}

var Groups = React.createClass({

    getInitialState: function() {
      return getGroupsFromStore();
    }

  , componentDidMount: function() {
      GroupsStore.addChangeListener( this.handleGroupsChange );
      GroupsMiddleware.requestGroupsList();
      GroupsMiddleware.subscribe();
    }

  , componentWillUnmount: function() {
      GroupsStore.removeChangeListener( this.handleGroupsChange );
      GroupsMiddleware.unsubscribe();
    }

  , handleGroupsChange: function() {
      this.setState( getGroupsFromStore() );
    }

  , render: function() {
      return <Viewer header     = { "Groups" }
                     inputData  = { this.state.groupsList }
                     viewData   = { viewData }
                     Editor     = { RouteHandler } />;
    }
});

module.exports = Groups;
