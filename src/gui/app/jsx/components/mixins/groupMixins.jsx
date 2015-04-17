// Group Editing Mixins
// ====================
// Groups-specific shared editing functions.
// TODO: Move anything in this and usersMixins that can be shared outside of the
// Accounts view into a more general mixin.

"use strict";

var _     = require("lodash");
var React = require("react");

var GroupsMiddleware = require("../../middleware/GroupsMiddleware");

module.exports = {

    contextTypes: {
        router: React.PropTypes.func
    }

  , deleteGroup: function(){
      GroupsMiddleware.deleteGroup(this.props.item["id"], this.returnToViewerRoot() );
    }
};