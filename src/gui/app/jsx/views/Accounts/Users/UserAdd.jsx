// Add User Template
// =================
// Handles the process of adding a new user. Provides an interface for
// setting up the configurable attributes of a new user.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import US from "../../../stores/UsersStore";
import UM from "../../../middleware/UsersMiddleware";

import GS from "../../../stores/GroupsStore";
import GM from "../../../middleware/GroupsMiddleware";

import inputHelpers from "../../../components/mixins/inputHelpers";
import userMixins from "../../../components/mixins/userMixins";
import groupMixins from "../../../components/mixins/groupMixins";
import viewerCommon from "../../../components/mixins/viewerCommon";


const UserAdd = React.createClass(
  { mixins: [ inputHelpers, userMixins, viewerCommon ]

  , contextTypes: {
    router: React.PropTypes.func
  }

  , propTypes:
    { itemSchema: React.PropTypes.object.isRequired
    , itemLabels: React.PropTypes.object.isRequired
    }

  , getInitialState: function () {
    return { nextUID: US.nextUID
           , newUser: {}
           , pleaseCreatePrimaryGroup : true };
  }

  , handleChange: function ( field, event ) {
    let newUser = this.state.newUser;

    if ( event.target.type == "checkbox" ) {
      newUser[ field ] = event.target.checked;
    } else {
      // TODO: using refs is bad, try to find a better way to get the
      // input out of a multi select if it exists
      switch ( this.props.itemSchema.properties[ field ].type ) {
        case "array": 
          newUser[ field ] = this.refs[ field ].getValue();
          break;
        case "integer":
        case "number":
          newUser[ field ] = _.parseInt( event.target.value );
          break;
        default:
          newUser[ field ] = event.target.value;
      }
    }
    this.setState( { newUser: newUser } );
  }

  , submitNewUser: function () {
    let params = {};
    let newUser = this.state.newUser;

    if ( _.has( newUser, "id" ) ) {
      newUser[ "id" ] = _.parseInt( newUser[ "id" ] );
    } else {
      newUser[ "id" ] = this.state.nextUID;
    }

    // If the user requests a new group, make one with the next
    // available GID and the username.
    if ( this.state.pleaseCreatePrimaryGroup ) {
      let newGID = GS.nextGID;
      console.log( newGID );
      GM.createGroup( { id   : newGID
                      , name : newUser[ "username" ] } );
      newUser[ "group" ] = newGID;
    }

    // Convert the array of strings provided by the form to an array of integers.
    if ( !_.isEmpty( newUser[ "groups" ] ) ) {
      newUser[ "groups" ] = this.parseGroupsArray( newUser[ "groups" ] );
    }

    UM.createUser( newUser );
  }

  , cancel: function () {
    this.context.router.transitionTo( "users" );
  }

  , reset: function () {
    this.setState( {newUser: {} } );
  }

  , primaryGroupToggle: function ( event ) {
    this.setState({
      pleaseCreatePrimaryGroup : event.target.checked
    });
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

    let submitUserButton =
      <TWBS.Button
        className = "pull-right"
        disabled  = { _.isEmpty( this.state.newUser ) }
        onClick   = { this.submitNewUser }
        bsStyle   = "info" >
        { "Create New User" }
      </TWBS.Button>;

    let buttonToolbar =
      <TWBS.ButtonToolbar>
        { cancelButton }
        { resetButton }
        { submitUserButton }
      </TWBS.ButtonToolbar>;

    let userIdField =
      <TWBS.Input
        type             = "text"
        label            = { "User ID" }
        value            = { this.state.newUser[ "id" ]
          ? this.state.newUser[ "id" ]
          : this.state.nextUID }
        onChange         = { this.handleChange.bind( null, "id" ) }
        key              = { "id" }
        ref              = "id"
        groupClassName   = { _.has( this.state.newUser["id"] )
          ? "editor-was-modified" : "" } />;

    let userNameField =
      <TWBS.Input
        type             = "text"
        label            = { "User Name" }
        value            = { this.state.newUser[ "username" ]
          ? this.state.newUser[ "username" ]
          : null }
        onChange         = { this.handleChange.bind( null, "username" ) }
        key              = { "username" }
        ref              = "username"
        groupClassName   = { _.has( this.state.newUser["username"] )
          ? "editor-was-modified" : "" } />;

    let userFullNameField =
      <TWBS.Input
        type             = "text"
        label            = { "Full Name" }
        value            = { this.state.newUser[ "full_name" ]
          ? this.state.newUser[ "full_name" ]
          : null }
        onChange         = { this.handleChange.bind( null, "full_name" ) }
        key              = { "full_name" }
        ref              = "full_name"
        groupClassName   = { _.has( this.state.newUser["full_name"] )
          ? "editor-was-modified" : "" } />;

    let userEmailField =
      <TWBS.Input
        type             = "text"
        label            = { "eMail" }
        value            = { this.state.newUser[ "email" ]
          ? this.state.newUser[ "email" ]
          : null }
        onChange         = { this.handleChange.bind( null, "email" ) }
        key              = { "email" }
        ref              = "email"
        groupClassName   = { _.has( this.state.newUser["email"] )
          ? "editor-was-modified" : "" } />;

    let userShellField =
      <TWBS.Input
        type             = "select"
        label            = { "Shell" }
        value     = { this.state.newUser[ "shell" ]
          ? this.state.newUser[ "shell" ]
          : null }
        onChange         = { this.handleChange.bind( null, "shell" ) }
        key              = { "shell" }
        ref              = "shell"
        groupClassName   = { _.has( this.state.newUser["shell"] )
          ? "editor-was-modified" : "" } >
        { this.generateOptionsList( this.state.shells, "name" ) }
      </TWBS.Input>;

    let userSshPubKeyField =
      <TWBS.Input
        type             = "textarea"
        label            = { "Public Key" }
        value            = { this.state.newUser["sshpubkey" ]
          ? this.state.newUser[ "sshpubkey" ]
          : null }
        onChange         = { this.handleChange.bind( null, "sshpubkey" ) }
        key              = { "sshpubkey" }
        ref              = "sshpubkey"
        groupClassName   = { _.has( this.state.newUser["sshpubkey"] )
          ? "editor-was-modified" : "" }
        rows             = "10" />;

    let userGroupsField =
      <TWBS.Input
        type             = "select"
        label            = "Other Groups"
        value            = { this.state.newUser[ "groups" ]
          ? this.state.newUser[ "groups" ]
          : null }
        onChange         = { this.handleChange.bind( null, "groups" ) }
        key              = { "groups" }
        ref              = "groups"
        groupClassName   = { _.has( this.state.newUser[ "groups" ] )
          ? "editor-was-modified" : "" }
        multiple >
        { this.generateOptionsList( GS.groups, "groupID", "groupName" ) }
      </TWBS.Input>;

    let userLockedField =
      <TWBS.Input
        type             = "checkbox"
        checked          = { this.state.newUser[ "locked" ]
          ? this.state.newUser["locked"]
          : null }
        label            = { "Locked" }
        onChange         = { this.handleChange.bind( null, "locked" ) }
        key              = { "locked" }
        ref              = "locked"
        groupClassName   = { _.has( this.state.newUser["locked"] )
          ? "editor-was-modified" : "" } />;

    let userSudoField =
      <TWBS.Input
        type             = "checkbox"
        checked          = { this.state.newUser[ "sudo" ]
          ? this.state.newUser[ "sudo" ]
          : null }
        label            = { "sudo" }
        onChange         = { this.handleChange.bind( null, "sudo" ) }
        key              = { "sudo" }
        ref              = "sudo"
        groupClassName   = { _.has( this.state.newUser[ "sudo" ] )
          ? "editor-was-modified" : "" } />;

    let userPasswordDisabledField =
      <TWBS.Input
        type             = "checkbox"
        label            = { "Password Disabled" }
        checked          = { this.state.newUser[ "password_disabled" ]
          ? this.state.newUser[ "password_disabled" ]
          : null }
        onChange = { this.handleChange.bind( null, "password_disabled" ) }
        key              = { "password_disabled" }
        ref              = "password_disabled"
        groupClassName = {
          _.has( this.state.newUser[ "password_disabled" ] )
          ? "editor-was-modified" : "" } />;

    let userAutoPrimaryGroupField =
      <TWBS.Input type             = "checkbox"
        label            = "Automatically Create Primary Group"
        ref              = "createPrimaryGroup"
        onChange         = { this.primaryGroupToggle }
        checked          = { this.state.pleaseCreatePrimaryGroup } />;

    let userPrimaryGroupField;

    if ( !this.state.pleaseCreatePrimaryGroup ) {
      userPrimaryGroupField =
        <TWBS.Input
          type             = "select"
          label            = { "Primary Group" }
          value            = { this.state.newUser[ "group" ]
                           ? this.state.newUser[ "group" ]
                           : null }
          onChange         = { this.handleChange.bind( null, "group" ) }
          key              = { "group" }
          ref              = "group"
          groupClassName   = { _.has( this.state.newUser[ "group" ] )
            ? "editor-was-modified" : "" } >
          { this.generateOptionsList( GS.groups, "groupID", "groupName" ) }
        </TWBS.Input>;
    }

    let textEditForm =
      <div>
        { userIdField }
        { userNameField }
        { userFullNameField }
        { userEmailField }
        { userShellField }
        { userPrimaryGroupField } 
        { userSshPubKeyField }
        { userGroupsField }
      </div>;

    let checkboxEditForm =
      <div>
        { userLockedField }
        { userSudoField }
        { userPasswordDisabledField }
        { userAutoPrimaryGroupField }
      </div>;

    return (
      <TWBS.Grid fluid>
        <TWBS.Row>
          <TWBS.Col xs = {12} >
            { buttonToolbar }
          </TWBS.Col>
        </TWBS.Row>
        <TWBS.Row>
          <TWBS.Col xs = {8} >
            { textEditForm }
          </TWBS.Col>
          <TWBS.Col xs = {4} >
            { checkboxEditForm }
          </TWBS.Col>
        </TWBS.Row>
      </TWBS.Grid>
    );
  }

});

export default UserAdd;
