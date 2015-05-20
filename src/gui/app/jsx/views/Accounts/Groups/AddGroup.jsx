// Add Group Template
// ==================
// Handles the process of adding a new group.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import GroupsStore from "../../../stores/GroupsStore";
import GroupsMiddleware from "../../../middleware/GroupsMiddleware";

import inputHelpers from "../../../components/mixins/inputHelpers";
import groupMixins from "../../../components/mixins/groupMixins";

const AddGroup = React.createClass({

    mixins: [   inputHelpers
              , groupMixins ]

  , contextTypes: {
      router: React.PropTypes.func
    }

  , propTypes: {
      viewData: React.PropTypes.object.isRequired
    }

  , getInitialState: function () {

      var groupsList = GroupsStore.getAllGroups();

      return {
          locallyModifiedValues : {}
        , dataKeys   : this.props.viewData.format.dataKeys
        , groupsList : groupsList
      };
    }

  , handleValueChange: function( key, event ) {
      var value = this.refs[key].getValue();
      var newLocallyModified = this.state.locallyModifiedValues;

      var dataKey = _.find(this.state.dataKeys, function( dataKey ) {
        return (dataKey.key === key);
      });

      newLocallyModified[ key ] = this.processFormInput( event, value, dataKey );

      this.setState( { locallyModifiedValues: newLocallyModified } );
    }

  , submitNewGroup: function () {
      var routing = this.props.viewData.routing;
      var newGroupValues = {};
      var params         = {};

      // Stage values for submission. Read-only values are not allowed.
      newGroupValues = this.removeReadOnlyFields( this.state.locallyModifiedValues, this.state.dataKeys );

      // Set up to forward the view to the created group.
      params[ routing[ "param" ] ] = newGroupValues[ "name" ];

      // Submit the new group and redirect the view to it.
      // TODO: Does this need additional input validation?
      // TODO: Only redirect if the group was actually created.
      GroupsMiddleware.createGroup( newGroupValues, this.context.router.transitionTo( routing[ "route" ], params) );

    }

    // TODO: There is probably room to genericize this into a mixin.
  , cancel: function () {
      this.context.router.transitionTo( "groups" );
    }

  , render: function () {
      var addButtons =
        <TWBS.ButtonToolbar>
          <TWBS.Button className = "pull-right"
                       onClick   = { this.cancel }
                       bsStyle   = "default">{"Cancel"}</TWBS.Button>
          <TWBS.Button className = "pull-right"
                       disabled  = { _.isEmpty( this.state.locallyModifiedValues ) }
                       onClick   = { this.submitNewGroup}
                       bsStyle   = "info">{"Save New Group"}</TWBS.Button>
        </TWBS.ButtonToolbar>;

      var inputFields =
        <form className = "form-horizontal">
          <TWBS.Grid fluid>
            <TWBS.Row>
              <TWBS.Col xs = {4}>
                {/* Group id */}
                <TWBS.Input type             = "text"
                            label            = "Group ID"
                            ref              = "id"
                            value            = { this.state.locallyModifiedValues["id"]? this.state.locallyModifiedValues["id"]: this.getNextGID() }
                            onChange         = { this.handleValueChange.bind( null, "id" ) }
                            groupClassName   = { _.has(this.state.locallyModifiedValues, "id") && !_.isEmpty(this.state.locallyModifiedValues["id"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
              </TWBS.Col>
              <TWBS.Col xs = {8}>
                {/* username */}
                <TWBS.Input type             = "text"
                            label            = "Group Name"
                            ref              = "name"
                            value            = { this.state.locallyModifiedValues["name"]? this.state.locallyModifiedValues["name"]: null }
                            onChange         = { this.handleValueChange.bind( null, "name" ) }
                            groupClassName   = { _.has(this.state.locallyModifiedValues, "name") && !_.isEmpty(this.state.locallyModifiedValues["name"]) ? "editor-was-modified" : ""  }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            required />
              </TWBS.Col>
            </TWBS.Row>
          </TWBS.Grid>
        </form>;


      return (
        <div className="viewer-item-info">
          <TWBS.Grid fluid>
            { addButtons }
            { inputFields }
          </TWBS.Grid>
        </div>
      );
    }
});

export default AddGroup;
