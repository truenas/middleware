// Group Editing Mixins
// ====================
// Groups-specific shared editing functions.
// TODO: Move anything in this and usersMixins that can be shared outside of the
// Accounts view into a more general mixin.

"use strict";

import _ from "lodash";

import GroupsStore from "../../stores/GroupsStore";
import GroupsMiddleware from "../../middleware/GroupsMiddleware";

module.exports = {

    componentDidMount: function (){
      GroupsStore.addChangeListener(this.updateGroupsListInState);
    }

  , componentWillUnMount: function () {
      GroupsStore.removeChangeListener(this.updateGroupsListInState);
    }

  , updateGroupsListInState: function (){
      var groupsList = GroupsStore.getAllGroups();
      this.setState({ groupsList: groupsList});
    }

    // Will return the first available GID above 1000 (to be used as a default).
  , getNextGID: function () {
      var groups = {};

      // Turn the array of groups into an object for easier GID checking.
      _.forEach(this.state.groupsList, function ( group ) {
        groups[ group [ "id" ] ] = group;
      });

      var nextGID = 1000;

      // loop until it finds a GID that's not in use
      while( _.has( groups, nextGID.toString() ) ){
        nextGID++;
      }

      return nextGID;

    }

  , deleteGroup: function (){
      GroupsMiddleware.deleteGroup(this.props.item["id"], this.returnToViewerRoot() );
    }
};