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
      var groupsList = GroupsStore.groups;
      this.setState({ groupsList: groupsList});
    }

  , deleteGroup: function () {
      GroupsMiddleware.deleteGroup( this.props.item[ "groupID" ]
                                  , this.returnToViewerRoot() );
    }
};