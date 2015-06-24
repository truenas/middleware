// USER EDIT TEMPLATE
// ==================
// The edit pane for a user item. Allows the current user to make changes to the
// user item.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import inputHelpers from "../../../components/mixins/inputHelpers";
import userMixins from "../../../components/mixins/userMixins";
import viewerCommon from "../../../components/mixins/viewerCommon";

import UsersMiddleware from "../../../middleware/UsersMiddleware";

import GroupsStore from "../../../stores/GroupsStore";

const UserEdit = React.createClass(
  { mixins: [ inputHelpers, userMixins, viewerCommon ]

  , propTypes: { item: React.PropTypes.object.isRequired }

  , getInitialState: function () {
      return { locallyModifiedValues : {}
             , mixedValues : this.props.item
             , lastSentValues : {}
             };
    }

    // TODO: Validate that input values are legitimate for their field. For example,
    // id should be a number.
  , submitUserUpdate: function () {
      // Make sure nothing read-only made it in somehow.
      var valuesToSend = this.state.locallyModifiedValues;

      // Convert the array of strings provided by the form to an array of integers.
      if ( !_.isEmpty( valuesToSend[ "groups" ] ) ) {
        valuesToSend[ "groups" ] = this.parseGroupsArray( valuesToSend[ "groups" ] );
      }

      // Only bother to submit an update if there is anything to update.
      if ( !_.isEmpty( valuesToSend ) ) {
        UsersMiddleware.updateUser( this.props.item[ "id" ], valuesToSend, this.submissionRedirect( valuesToSend ) );

        // Save a record of the last changes we sent.
        this.setState({ lastSentValues: valuesToSend });
      } else {
        console.warn( "Attempted to send a User update with no valid fields." );
      }

    }

    // TODO: Currently this section just arbitrarily handles every property the
    // middleware sends in the order the browser sends it. This should be updated
    // to have a deliberate design.
    // TODO: Add alerts when a remote administrator has changed items that the
    // local administrator is also working on.
  , render: function () {
      var builtInUserAlert  = null;
      var editButtons       = null;
      var inputForm         = null;

      if ( this.props.item["builtin"] ) {
        builtInUserAlert = (
          <TWBS.Alert
            bsStyle   = "warning"
            className = "text-center"
          >
            <b>{"You should only edit a system user account if you know exactly what you're doing."}</b>
          </TWBS.Alert>
        );
      }

      editButtons =
        <TWBS.ButtonToolbar>
            <TWBS.Button
              className = "pull-left"
              disabled  = { this.props.item["builtin"] }
              onClick   = { this.deleteUser }
              bsStyle   = "danger" >
              {"Delete User"}
            </TWBS.Button>
            <TWBS.Button
              className = "pull-right"
              onClick   = { this.props.handleViewChange.bind( null, "view" ) }
              bsStyle   = "default" >
              {"Cancel"}
            </TWBS.Button>
            <TWBS.Button
              className = "pull-right"
              disabled  = { _.isEmpty( this.state.locallyModifiedValues ) }
              onClick   = { this.submitUserUpdate }
              bsStyle   = "info" >
              {"Save Changes"}
            </TWBS.Button>
        </TWBS.ButtonToolbar>;

      inputForm =
        <form className = "form-horizontal">
          <TWBS.Grid fluid>
            <TWBS.Row>
              <TWBS.Col xs = {8}>
                {/* User id */}
                <TWBS.Input
                  type             = "text"
                  label            = { "User ID" }
                  defaultValue     = { this.props.item[ "id" ] }
                  onChange         = { this.editHandleValueChange.bind( null, "id" ) }
                  key              = { "id" }
                  ref              = "id"
                  groupClassName   = { _.has( this.state.locallyModifiedValues["id"] ) ? "editor-was-modified" : "" }
                  labelClassName   = "col-xs-4"
                  wrapperClassName = "col-xs-8"
                />
                {/* username */}
                <TWBS.Input
                  type             = "text"
                  label            = { "User Name" }
                  defaultValue     = { this.props.item[ "username" ] }
                  onChange         = { this.editHandleValueChange.bind( null, "username" ) }
                  key              = { "username" }
                  ref              = "username"
                  groupClassName   = { _.has( this.state.locallyModifiedValues["username"] ) ? "editor-was-modified" : "" }
                  labelClassName   = "col-xs-4"
                  wrapperClassName = "col-xs-8"
                />
                {/* full_name*/}
                <TWBS.Input
                  type             = "text"
                  label            = { "Full Name" }
                  defaultValue     = { this.props.item[ "full_name" ] }
                  onChange         = { this.editHandleValueChange.bind( null, "full_name" ) }
                  key              = { "full_name" }
                  ref              = "full_name"
                  groupClassName   = { _.has( this.state.locallyModifiedValues["full_name"] ) ? "editor-was-modified" : "" }
                  labelClassName   = "col-xs-4"
                  wrapperClassName = "col-xs-8"
                />
                {/* email */}
                <TWBS.Input
                  type             = "text"
                  label            = { "email" }
                  defaultValue     = { this.props.item[ "email" ] }
                  onChange         = { this.editHandleValueChange.bind( null, "email" ) }
                  key              = { "email" }
                  ref              = "email"
                  groupClassName   = { _.has( this.state.locallyModifiedValues["email"] ) ? "editor-was-modified" : "" }
                  labelClassName   = "col-xs-4"
                  wrapperClassName = "col-xs-8"
                />
                {/* shell */}
                <TWBS.Input
                  type             = "select"
                  label            = { "Shell" }
                  defaultValue     = { this.props.item[ "shell" ] }
                  onChange         = { this.editHandleValueChange.bind( null, "shell" ) }
                  key              = { "shell" }
                  ref              = "shell"
                  groupClassName   = { _.has( this.state.locallyModifiedValues["shell"] ) ? "editor-was-modified" : "" }
                  labelClassName   = "col-xs-4"
                  wrapperClassName = "col-xs-8" >
                            { this.generateOptionsList( this.state.shells, "name" ) }
                </TWBS.Input>
                {/* primary group */}
                <TWBS.Input
                  type             = "select"
                  label            = { "Primary Group" }
                  defaultValue     = { this.props.item[ "group" ] }
                  onChange         = { this.editHandleValueChange.bind( null, "group" ) }
                  key              = { "group" }
                  ref              = "group"
                  groupClassName   = { _.has( this.state.locallyModifiedValues["group"] ) ? "editor-was-modified" : "" }
                  labelClassName   = "col-xs-4"
                  wrapperClassName = "col-xs-8" >
                  { this.generateOptionsList( GroupsStore.groups, "id", "name" ) }
                </TWBS.Input>
                {/* sshpubkey */}
                <TWBS.Input
                  type             = "textarea"
                  label            = { "Public Key" }
                  defaultValue     = { this.props.item[ "sshpubkey" ] }
                  onChange         = { this.editHandleValueChange.bind( null, "sshpubkey" ) }
                  key              = { "sshpubkey" }
                  ref              = "sshpubkey"
                  groupClassName   = { _.has( this.state.locallyModifiedValues["sshpubkey"] ) ? "editor-was-modified" : "" }
                  labelClassName   = "col-xs-4"
                  wrapperClassName = "col-xs-8"
                            rows             = "10" >
                </TWBS.Input>
                {/* Other Groups */}
                <TWBS.Input
                  type             = "select"
                  label            = "Other Groups"
                  defaultValue     = { this.props.item[ "groups" ] }
                  onChange         = { this.editHandleValueChange.bind( null, "groups" ) }
                  key              = "groups"
                  ref              = "groups"
                  groupClassName   = { _.has( this.state.locallyModifiedValues[ "groups" ] ) ? "editor-was-modified" : "" }
                  labelClassName   = "col-xs-4"
                  wrapperClassName = "col-xs-8"
                            multiple >
                            { this.generateOptionsList( GroupsStore.groups, "id", "name" ) }
                </TWBS.Input>
              </TWBS.Col>
              <TWBS.Col xs = {4}>
                {/* locked */}
                <TWBS.Input
                  type             = "checkbox"
                  checked          = { this.state.mixedValues["locked"] }
                  label            = { "Locked" }
                  value            = { this.state.mixedValues["locked"] ? this.state.mixedValues["locked"] : "" }
                  defaultValue     = { this.props.item[ "locked" ] }
                  onChange         = { this.editHandleValueChange.bind( null, "locked" ) }
                  key              = { "locked" }
                  groupClassName   = { _.has( this.state.locallyModifiedValues["locked"] ) ? "editor-was-modified" : "" }
                  ref              = "locked"
                  labelClassName   = "col-xs-4"
                  wrapperClassName = "col-xs-8"
                />
                {/* sudo */}
                <TWBS.Input
                  type             = "checkbox"
                  checked          = { this.state.mixedValues["sudo"] }
                  label            = { "sudo" }
                  value            = { this.state.mixedValues["sudo"] ? this.state.mixedValues["sudo"] : "" }
                  defaultValue     = { this.props.item[ "sudo" ] }
                  onChange         = { this.editHandleValueChange.bind( null, "sudo" ) }
                  key              = { "sudo" }
                  groupClassName   = { _.has( this.state.locallyModifiedValues["sudo"] ) ? "editor-was-modified" : "" }
                  ref              = "sudo"
                  labelClassName   = "col-xs-4"
                  wrapperClassName = "col-xs-8"
                />
                {/* password_disabled */}
                <TWBS.Input
                  type             = "checkbox"
                  label            = { "password_disabled" }
                  checked          = { this.state.mixedValues["password_disabled"] }
                  value            = { this.state.mixedValues["password_disabled"] ? this.state.mixedValues["password_disabled"] : "" }
                  defaultValue     = { this.props.item[ "password_disabled" ] }
                  onChange         = { this.editHandleValueChange.bind( null, "password_disabled" ) }
                  key              = { "password_disabled" }
                  groupClassName   = { _.has( this.state.locallyModifiedValues["password_disabled"] ) ? "editor-was-modified" : "" }
                  ref              = "password_disabled"
                  labelClassName   = "col-xs-4"
                  wrapperClassName = "col-xs-8"
                />
                {/* logged-in */}
                <TWBS.Input
                  type             = "checkbox"
                  checked          = { this.state.mixedValues["logged-in"] }
                  label            = { "logged-in" }
                  value            = { this.state.mixedValues["logged-in"] ? this.state.mixedValues["logged-in"] : "" }
                  defaultValue     = { this.props.item[ "logged-in" ] }
                  onChange         = { this.editHandleValueChange.bind( null, "logged-in" ) }
                  key              = { "logged-in" }
                  groupClassName   = { _.has( this.state.locallyModifiedValues["logged-in"] ) ? "editor-was-modified" : "" }
                  ref              = "logged-in"
                  labelClassName   = "col-xs-4"
                  wrapperClassName = "col-xs-8"
                />
              </TWBS.Col>
            </TWBS.Row>
          </TWBS.Grid>
        </form>;

      return (
        <TWBS.Grid fluid>
          {/* Save and Cancel Buttons - Top */}
          { editButtons }

          {/* Shows a warning if the user account is built in */}
          { builtInUserAlert }

          { inputForm }

          {/* Save and Cancel Buttons - Bottom */}
          { editButtons }
        </TWBS.Grid>
      );
    }
  }
);

export default UserEdit;
