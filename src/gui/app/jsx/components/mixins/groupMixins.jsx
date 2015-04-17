// Group Editing Mixins
// ====================
// Groups-specific shared editing functions.
// TODO: Move anything in this and usersMixins that can be shared outside of the
// Accounts view into a more general mixin.

"use strict";

var _     = require("lodash");
var React = require("react");

var GroupsStore      = require("../../stores/GroupsStore");
var GroupsMiddleware = require("../../middleware/GroupsMiddleware");

module.exports = {


    // Will return the first available GID above 1000 (to be used as a default).
  , getNextGID: function() {
      var groups = GroupsStore.getAllGroups();

      var nextGID = 1000;

      // loop until it finds a GID that's not in use
      while( _.has( groups, nextGID ) ){
        nextGID++;
      }

      return nextGID;

    }

  , deleteGroup: function(){
      GroupsMiddleware.deleteGroup(this.props.item["id"], this.returnToViewerRoot() );
    }
};