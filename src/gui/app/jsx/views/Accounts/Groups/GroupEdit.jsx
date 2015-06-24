// Groups Editor Component
// =======================
// The edit pane for an individual group.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import GM from "../../../middleware/GroupsMiddleware";
import GS from "../../../stores/GroupsStore";

import US from "../../../stores/UsersStore";


const GroupEdit = React.createClass(

  { propTypes:
    { itemSchema: React.PropTypes.object.isRequired
    , itemLabels: React.PropTypes.object.isRequired
    , item: React.PropTypes.object.isRequired
    }

  , contextTypes: { router: React.PropTypes.func }

  , getInitialState: function () {
    return { modifiedValues: {}
           , remoteValues: this.props.item
           };
  }

  , resetChanges: function () {
    this.setState( { modifiedValues: {} } );
  }

  , handleChange: function ( field, event ) {
    let newModifiedValues = this.state.modifiedValues;
    newModifiedValues[ field ] = event.target.value;
    this.setState( { modifiedValues: newModifiedValues } );
  }

  , render: function () {
    let builtInWarning = null;

    if ( this.props.item[ "builtIn" ] ) {
      builtInWarning =
        <TWBS.Alert
          bsStyle = { "warning" }
          className = { "text-center built-in-warning" } >
          { "This is a built-in system group. Only edit this group if you "
          + "know exactly what you are doing." }
        </TWBS.Alert>;
    }

    let groupNameValue = this.state.modifiedValues[ "groupName" ]
                      || this.state.remoteValues[ "groupName" ];

    let groupNameClass = this.state.modifiedValues[ "groupName" ]
                       ? "editor-was-modified"
                       : "";

    let groupNameField =
      <TWBS.Input
        className = { groupNameClass }
        type = "text"
        label = "Group Name"
        value = { groupNameValue }
        onChange = { this.handleChange.bind( null, "groupName" ) } />;

    let resetButton =
      <TWBS.Button
        className = "pull-right"
        bsStyle = "warning"
        onClick = { this.resetChanges } >
        { "Reset Changes" }
      </TWBS.Button>;

    let submitButton =
      <TWBS.Button
        className = "pull-right"
        bsStyle = "success" >
        { "Submit Changes" }
      </TWBS.Button>;

    let cancelButton =
      <TWBS.Button
        className = "pull-left"
        bsStyle = "default" >
        { "Cancel Edit" }
      </TWBS.Button>;

    let deletebutton =
      <TWBS.Button
        className = "pull-left"
        bsStyle = "danger"
        disabled = { this.props.item[ "builtIn" ] } >
        { "Delete Group" }
      </TWBS.Button>;

    let buttonToolbar =
      <TWBS.ButtonToolbar >
        { cancelButton }
        { deletebutton }
        { resetButton }
        { submitButton }
      </TWBS.ButtonToolbar>;

    let editForm =
      <div>
        { groupNameField }
      </div>;

    let groupIDDisplay =
      <div>
        <strong>
          { this.props.itemLabels.properties[ "groupID" ] + ": " }
        </strong>
        { this.props.item[ "groupID" ] }
      </div>;

    return (
      <TWBS.Grid fluid >
        <TWBS.Row>
          <TWBS.Col
            xs = { 12 } >
            { buttonToolbar }
          </TWBS.Col>
        </TWBS.Row>
        <TWBS.Row>
          <TWBS.Col
            xs = { 12 } >
            { builtInWarning }
          </TWBS.Col>
        </TWBS.Row>
        <TWBS.Row>
          <TWBS.Col
            xs = { 12 }
            sm = { 6 } >
            { editForm }
          </TWBS.Col>
          <TWBS.Col
            xs = { 12 }
            sm = { 6 } >
            { groupIDDisplay }
          </TWBS.Col>
        </TWBS.Row>
      </TWBS.Grid>
    );
  }

});

export default GroupEdit;
