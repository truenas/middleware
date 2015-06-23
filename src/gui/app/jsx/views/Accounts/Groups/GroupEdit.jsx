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

  , render: function () {
    let builtInWarning = null;
    let groupIDDisplay = null;
    let groupNameField = null;
    let editForm = null;
    let buttonToolbar = null;
    let resetButton = null;
    let submitButton = null;
    let cancelButton = null;
    let deletebutton = null;

    if ( this.props.item[ "builtIn" ] ) {
      builtInWarning =
        <TWBS.Alert
          bsStyle = { "warning" }
          className = { "text-center" } >
          { "This is a built-in system group. Only edit this group if you "
          + "know exactly what you are doing." }
        </TWBS.Alert>;
    }

    groupNameField =
      <TWBS.Input
        type = "text"
        label = "Group Name" >
      </TWBS.Input>;

    resetButton =
      <TWBS.Button
        className = "pull-right"
        bsStyle = "warning" >
        { "Reset Changes" }
      </TWBS.Button>;

    submitButton =
      <TWBS.Button
        className = "pull-right"
        bsStyle = "success" >
        { "Submit Changes" }
      </TWBS.Button>;

    cancelButton =
      <TWBS.Button
        className = "pull-left"
        bsStyle = "default" >
        { "Cancel Edit" }
      </TWBS.Button>;

    deletebutton =
      <TWBS.Button
        className = "pull-left"
        bsStyle = "danger"
        disabled = { this.props.item[ "builtIn" ] } >
        { "Delete Group" }
      </TWBS.Button>;

    buttonToolbar =
      <TWBS.ButtonToolbar
        className = "editor-button-toolbar" >
        { cancelButton }
        { deletebutton }
        { resetButton }
        { submitButton }
      </TWBS.ButtonToolbar>;

    editForm =
      <div>
        { groupNameField }
      </div>;

    groupIDDisplay =
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
