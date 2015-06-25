// Add Group Template
// ==================
// Handles the process of adding a new group.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import GS from "../../../stores/GroupsStore";
import GM from "../../../middleware/GroupsMiddleware";


const AddGroup = React.createClass({

  contextTypes: {
      router: React.PropTypes.func
    }

  , propTypes:
    { itemSchema: React.PropTypes.object.isRequired
    , itemLabels: React.PropTypes.object.isRequired
    }

  , getInitialState: function () {
    return { nextGID: GS.nextGID
           , newGroup: {} };
  }

  , handleChange: function ( field, event ) {
    let newGroup = this.state.newGroup;
    newGroup[ field ] = event.target.value;
    this.setState( { newGroup: newGroup } );
  }

  , submitNewGroup: function () {
    let newGroup = GS.reverseKeyTranslation( this.state.newGroup );
    if ( !newGroup[ "groupID" ] ) {
      newGroup[ "groupID" ] = this.state.nextGID;
    }

    GM.createGroup( newGroup );
  }

  , cancel: function () {
    this.context.router.transitionTo( "groups" );
  }

  , reset: function () {
    this.setState( { newGroup: {} } );
  }

  , render: function () {

    let cancelButton =
      <TWBS.Button
        className = "pull-left"
        onClick   = { this.cancel }
        bsStyle   = "default" >
        { "Cancel" }
      </TWBS.Button>;

    let resetButton =
      <TWBS.Button
        className = "pull-left"
        bsStyle = "warning"
        onClick = { this.reset } >
        { "Reset Changes" }
      </TWBS.Button>;

    let submitGroupButton =
      <TWBS.Button
        className = "pull-right"
        disabled  = { _.isEmpty( this.state.newGroup ) }
        onClick   = { this.submitNewGroup }
        bsStyle   = "info" >
        { "Create New Group" }
      </TWBS.Button>;

    let buttonToolbar =
      <TWBS.ButtonToolbar>
        { cancelButton }
        { resetButton }
        { submitGroupButton }
      </TWBS.ButtonToolbar>;

    let inputFields =
      <TWBS.Row>
        <TWBS.Col xs = {4}>
          {/* Group id */}
          <TWBS.Input
            type             = "text"
            label            = { this.props.itemLabels.properties[ "groupID" ] }
            value            = { this.state.newGroup[ "groupID" ]
                               ? this.state.newGroup[ "groupID" ]
                               : this.state.nextGID }
            onChange         = { this.handleChange.bind( null, "groupID" ) }
            className   = { _.has( this.state.newGroup, "groupID" )
                              && !_.isEmpty( this.state.newGroup[ "id" ] )
                               ? "editor-was-modified"
                               : "" } />
        </TWBS.Col>
        <TWBS.Col xs = {8}>
          {/* username */}
          <TWBS.Input
            type             = "text"
            label            = { this.props.itemLabels.properties[ "groupName" ] }
            value            = { this.state.newGroup[ "groupName" ]
                               ? this.state.newGroup[ "groupName" ]
                               : null }
            onChange         = { this.handleChange.bind( null, "groupName" ) }
            className   = { _.has( this.state.newGroup, "groupName" )
                              && !_.isEmpty( this.state.newGroup[ "groupName" ] )
                               ? "editor-was-modified"
                               : "" } />
        </TWBS.Col>
      </TWBS.Row>;


    return (
      <div className="viewer-item-info">
        <TWBS.Grid fluid>
          <TWBS.Row>
            <TWBS.Col xs = {12}>
              { buttonToolbar }
            </TWBS.Col>
          </TWBS.Row>
          { inputFields }
        </TWBS.Grid>
      </div>
    );
  }
});

export default AddGroup;
