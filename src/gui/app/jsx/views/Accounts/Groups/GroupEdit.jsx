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
    let resetButton = null;
    let submitButton = null;

    if ( this.props.item[ "builtIn" ] ) {
      builtInWarning =
        <TWBS.Row>
          <TWBS.Col xs = { 12 } >
            <TWBS.Alert
              bsStyle = { "warning" }
              className = { "text-center" } >
              { "This is a built-in system group. Only edit this group if you "
              + "know exactly what you are doing." }
            </TWBS.Alert>
          </TWBS.Col>
        </TWBS.Row>;
    }

    groupNameField =
      <TWBS.Input
        type = { "text" }
        ref = { "groupName" } >
      </TWBS.Input>;

    resetButton =
      <TWBS.Button
        bsStyle = "warning" > { "Reset" }
      </TWBS.Button>;

    submitButton =
      <TWBS.ButtonInput
        bsStyle = "success" >
        { "Submit" }
      </TWBS.ButtonInput>;

    editForm =
      <TWBS.Col
        xs = { 12 }
        sm = { 6 } >
          { groupNameField }
      </TWBS.Col>;

    groupIDDisplay =
      <TWBS.Col
        xs = { 12 }
        sm = { 6 } >
        { "Group ID: " }
        { this.props.item[ "groupID" ] }
      </TWBS.Col>;

    return (
      <TWBS.Grid fluid >
        { builtInWarning }
        <TWBS.Row>
          { editForm }
          { groupIDDisplay }
        </TWBS.Row>
      </TWBS.Grid>
    );
  }

});

export default GroupEdit;
