// User Item Template
// ==================
// Handles the viewing and editing of individual user items. Shows a non-editable
// overview of the user account, and mode-switches to a more standard editor
// panel. User is set by providing a route parameter.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import routerShim from "../../../components/mixins/routerShim";
import clientStatus from "../../../components/mixins/clientStatus";

import viewerUtil from "../../../components/Viewer/viewerUtil";
import editorUtil from "../../../components/Viewer/Editor/editorUtil";

import UsersMiddleware from "../../../middleware/UsersMiddleware";
import UsersStore from "../../../stores/UsersStore";

import GroupsStore from "../../../stores/GroupsStore";

import inputHelpers from "../../../components/mixins/inputHelpers";
import userMixins from "../../../components/mixins/userMixins";
import viewerCommon from "../../../components/mixins/viewerCommon";

// OVERVIEW PANE
const UserView = React.createClass({

    mixins: [  userMixins
             , viewerCommon ]

  , contextTypes: {
        router: React.PropTypes.func
    }

  , propTypes: {
      item: React.PropTypes.object.isRequired
    }

  , getGroupName: function(groupID) {
      var group = GroupsStore.getGroup(groupID);

      if ( group ) {
        return group.name;
      } else {
        // TODO: Have a policy to deal with a user assigned to a nonexistant group.
        return null;
      }
    }

  , createGroupDisplayList: function (){
      var listGroupItemArray = [] ;

      listGroupItemArray = _.map( this.props.item[ "groups" ], function( groupID ){
        var displayItem = null;
        var group = GroupsStore.getGroup( groupID );

        if ( group ){
          displayItem = <TWBS.ListGroupItem>{ group.name }</TWBS.ListGroupItem>;
        }

        return displayItem;
      }, this );

      return listGroupItemArray;
  }

  , render: function () {
      var builtInUserAlert = null;
      var editButtons      = null;

      if ( this.props.item["builtin"] ) {
        builtInUserAlert = (
          <TWBS.Alert bsStyle   = "info"
                      className = "text-center">
            <b>{"This is a built-in FreeNAS user account."}</b>
          </TWBS.Alert>
        );
      }

      editButtons = (
        <TWBS.ButtonToolbar>
            <TWBS.Button className = "pull-left"
                         disabled  = { this.props.item["builtin"] }
                         onClick   = { this.deleteUser }
                         bsStyle   = "danger" >{"Delete User"}</TWBS.Button>
            <TWBS.Button className = "pull-right"
                         onClick   = { this.props.handleViewChange.bind(null, "edit") }
                         bsStyle   = "info" >{"Edit User"}</TWBS.Button>
        </TWBS.ButtonToolbar>
      );

      return (
        <TWBS.Grid fluid>
          {/* "Edit User" Button - Top */}
          { editButtons }

          {/* User icon and general information */}
          <TWBS.Row>
            <TWBS.Col xs={3}
                      className="text-center">
              <viewerUtil.ItemIcon primaryString   = { this.props.item["full_name"] }
                                   fallbackString  = { this.props.item["username"] }
                                   iconImage       = { this.props.item["user_icon"] }
                                   seedNumber      = { this.props.item["id"] } />
            </TWBS.Col>
            <TWBS.Col xs={9}>
              <h3>{ this.props.item["username"] }</h3>
              <h4 className="text-muted">{ viewerUtil.writeString( this.props.item["full_name"], "\u200B" ) }</h4>
              <h4 className="text-muted">{ viewerUtil.writeString( this.props.item["email"], "\u200B" ) }</h4>
              <hr />
            </TWBS.Col>
          </TWBS.Row>

          {/* Shows a warning if the user account is built in */}
          { builtInUserAlert }

          {/* Primary user data overview */}
          <TWBS.Row>
            <viewerUtil.DataCell title  = { "User ID" }
                                 colNum = { 3 }
                                 entry  = { this.props.item["id"] } />
            <viewerUtil.DataCell title  = { "Primary Group" }
                                 colNum = { 3 }
                                 entry  = { this.getGroupName(this.props.item["group"]) } />
            <viewerUtil.DataCell title  = { "Shell" }
                                 colNum = { 3 }
                                 entry  = { this.props.item["shell"] } />
            <viewerUtil.DataCell title  = { "Locked Account" }
                                 colNum = { 3 }
                                 entry  = { this.props.item["locked"] ? this.props.item["locked"] : false } />
            <viewerUtil.DataCell title  = { "Sudo Access" }
                                 colNum = { 3 }
                                 entry  = { this.props.item["sudo"] ? this.props.item["sudo"]: false } />
            <viewerUtil.DataCell title  = { "Password Disabled" }
                                 colNum = { 3 }
                                 entry  = { this.props.item["password_disabled"] ? this.props.item["password_disabled"]: false } />
            <viewerUtil.DataCell title  = { "Logged In" }
                                 colNum = { 3 }
                                 entry  = { this.props.item["logged-in"] ? this.props.item["logged-in"]: false } />
            <viewerUtil.DataCell title  = { "Home Directory" }
                                 colNum = { 3 }
                                 entry  = { this.props.item["home"] } />
            <viewerUtil.DataCell title  = { "email" }
                                 colNum = { 3 }
                                 entry  = { this.props.item["email"] ? this.props.item["email"]: "" } />
            <TWBS.Col xs        = {12}
                      className ="text-muted" >
                        <h4 className = "text-muted" >{ "Other Groups" }</h4>
                        <TWBS.ListGroup>
                          { this.createGroupDisplayList() }
                        </TWBS.ListGroup>
            </TWBS.Col>
          </TWBS.Row>

          {/* "Edit User" Button - Bottom */}
          { editButtons }

        </TWBS.Grid>
      );
    }

});


// EDITOR PANE
const UserEdit = React.createClass({

  mixins: [ inputHelpers
          , userMixins
          , viewerCommon ]

  , contextTypes: {
      router: React.PropTypes.func
    }

  , propTypes: { item : React.PropTypes.object.isRequired
               , viewData : React.PropTypes.object.isRequired
               }

  , getInitialState: function () {
      var remoteState = this.setRemoteState( this.props );

      return { locallyModifiedValues : {}
             , remotelyModifiedValues : {}
             , remoteState : remoteState
             , mixedValues : this.props.item
             , lastSentValues : {}
             , dataKeys : this.props.viewData["format"]["dataKeys"]
      };
    }

  , componentWillReceiveProps: function( nextProps ) {
      var newRemoteModified  = {};
      var newLocallyModified = {};
      var dataKeys = nextProps.viewData["format"]["dataKeys"];

      // remotelyModifiedValues represents everything that's changed remotely
      // since the view was opened. This is the difference between the newly arriving
      // props and the initial ones. Read-only and unknown values are ignored.
      // TODO: Use this to show alerts for remote changes on sections the local
      // administrator is working on.
      var mismatchedRemoteFields = _.pick(nextProps.item, function( value, key ) {
        return _.isEqual( this.state.remoteState[ key ], value );
      }, this);

      newRemoteModified = this.removeReadOnlyFields( mismatchedRemoteFields, dataKeys);

      // remoteState records the item as it was when the view was first
      // opened. This is used to mark changes that have occurred remotely since
      // the user began editing.
      // It is important to know if the incoming change resulted from a call
      // made by the local administrator. When this happens, we reset the
      // remoteState to get rid of remote edit markers, as the local version
      // has thus become authoritative.
      // We check this by comparing the incoming changes (newRemoteModified) to the
      // last request sent (this.state.lastSentValues). If this check succeeds,
      // we reset newLocallyModified and newRemoteModified, as there are no longer
      // any remote or local changes to record.
      // TODO: Do this in a deterministic way, instead of relying on comparing
      // values.
      if (_.isEqual(this.state.lastSentValues, newRemoteModified)){
          newRemoteModified  = {};
          newLocallyModified = {};
          this.setState ({
              remoteState           : this.setRemoteState(nextProps)
            , locallyModifiedValues : newLocallyModified
          });
      }

      this.setState({
          remotelyModifiedValues : newRemoteModified
      });
    }

    // TODO: Validate that input values are legitimate for their field. For example,
    // id should be a number.
  , submitUserUpdate: function () {
      // Make sure nothing read-only made it in somehow.
      var valuesToSend = this.removeReadOnlyFields( this.state.locallyModifiedValues, this.state.dataKeys );

      // Convert the array of strings provided by the form to an array of integers.
      if( !_.isEmpty( valuesToSend[ "groups" ] ) ){
        valuesToSend[ "groups" ] = this.parseGroupsArray( valuesToSend[ "groups" ] );
      }

      // Only bother to submit an update if there is anything to update.
      if (!_.isEmpty( valuesToSend ) ){
        UsersMiddleware.updateUser( this.props.item[ "id" ], valuesToSend, this.submissionRedirect( valuesToSend ) );

        // Save a record of the last changes we sent.
        this.setState({
            lastSentValues : valuesToSend
        });
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
          <TWBS.Alert bsStyle   = "warning"
                      className = "text-center">
            <b>{"You should only edit a system user account if you know exactly what you're doing."}</b>
          </TWBS.Alert>
        );
      }

      editButtons =
        <TWBS.ButtonToolbar>
            <TWBS.Button className = "pull-left"
                         disabled  = { this.props.item["builtin"] }
                         onClick   = { this.deleteUser }
                         bsStyle   = "danger" >{"Delete User"}</TWBS.Button>
            <TWBS.Button className = "pull-right"
                         onClick   = { this.props.handleViewChange.bind(null, "view") }
                         bsStyle   = "default" >{"Cancel"}</TWBS.Button>
            <TWBS.Button className = "pull-right"
                         disabled  = { _.isEmpty( this.state.locallyModifiedValues ) ? true : false }
                         onClick   = { this.submitUserUpdate }
                         bsStyle   = "info" >{"Save Changes"}</TWBS.Button>
        </TWBS.ButtonToolbar>;

      inputForm =
        <form className = "form-horizontal">
          <TWBS.Grid fluid>
            <TWBS.Row>
              <TWBS.Col xs = {8}>
                {/* User id */}
                <TWBS.Input type             = "text"
                            label            = { "User ID" }
                            defaultValue     = { this.props.item[ "id" ] }
                            onChange         = { this.editHandleValueChange.bind( null, "id" ) }
                            key              = { "id" }
                            ref              = "id"
                            groupClassName   = { _.has(this.state.locallyModifiedValues["id"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* username */}
                <TWBS.Input type             = "text"
                            label            = { "User Name" }
                            defaultValue     = { this.props.item[ "username" ] }
                            onChange         = { this.editHandleValueChange.bind( null, "username" ) }
                            key              = { "username" }
                            ref              = "username"
                            groupClassName   = { _.has(this.state.locallyModifiedValues["username"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* full_name*/}
                <TWBS.Input type             = "text"
                            label            = { "Full Name" }
                            defaultValue     = { this.props.item[ "full_name" ] }
                            onChange         = { this.editHandleValueChange.bind( null, "full_name" ) }
                            key              = { "full_name" }
                            ref              = "full_name"
                            groupClassName   = { _.has(this.state.locallyModifiedValues["full_name"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* email */}
                  <TWBS.Input type             = "text"
                            label            = { "email" }
                            defaultValue     = { this.props.item[ "email" ] }
                            onChange         = { this.editHandleValueChange.bind( null, "email" ) }
                            key              = { "email" }
                            ref              = "email"
                            groupClassName   = { _.has(this.state.locallyModifiedValues["email"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* shell */}
                <TWBS.Input type             = "select"
                            label            = { "Shell" }
                            defaultValue     = { this.props.item[ "shell" ] }
                            onChange         = { this.editHandleValueChange.bind( null, "shell" ) }
                            key              = { "shell" }
                            ref              = "shell"
                            groupClassName   = { _.has(this.state.locallyModifiedValues["shell"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" >
                            { this.generateOptionsList( this.state.shells, "name" ) }
                </TWBS.Input>
                {/* primary group */}
                <TWBS.Input type             = "select"
                            label            = { "Primary Group" }
                            defaultValue     = { this.props.item[ "group" ] }
                            onChange         = { this.editHandleValueChange.bind( null, "group" ) }
                            key              = { "group" }
                            ref              = "group"
                            groupClassName   = { _.has(this.state.locallyModifiedValues["group"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" >
                            { this.generateOptionsList( GroupsStore.getAllGroups(), "id", "name" ) }
                </TWBS.Input>
                {/* sshpubkey */}
                <TWBS.Input type             = "textarea"
                            label            = { "Public Key" }
                            defaultValue     = { this.props.item[ "sshpubkey" ] }
                            onChange         = { this.editHandleValueChange.bind( null, "sshpubkey" ) }
                            key              = { "sshpubkey" }
                            ref              = "sshpubkey"
                            groupClassName   = { _.has(this.state.locallyModifiedValues["sshpubkey"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            rows             = "10" >
                </TWBS.Input>
                {/* Other Groups */}
                <TWBS.Input type             = "select"
                            label            = "Other Groups"
                            defaultValue     = { this.props.item[ "groups" ] }
                            onChange         = { this.editHandleValueChange.bind( null, "groups" ) }
                            key              = "groups"
                            ref              = "groups"
                            groupClassName   = { _.has(this.state.locallyModifiedValues[ "groups" ]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            multiple >
                            { this.generateOptionsList( GroupsStore.getAllGroups(), "id", "name" ) }
                </TWBS.Input>
              </TWBS.Col>
              <TWBS.Col xs = {4}>
                {/* locked */}
                <TWBS.Input type             = "checkbox"
                            checked          = { this.state.mixedValues["locked"] }
                            label            = { "Locked" }
                            value            = { this.state.mixedValues["locked"] ? this.state.mixedValues["locked"] : "" }
                            defaultValue     = { this.props.item[ "locked" ] }
                            onChange         = { this.editHandleValueChange.bind( null, "locked" ) }
                            key              = { "locked" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["locked"]) ? "editor-was-modified" : "" }
                            ref              = "locked"
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* sudo */}
                <TWBS.Input type             = "checkbox"
                            checked          = { this.state.mixedValues["sudo"] }
                            label            = { "sudo" }
                            value            = { this.state.mixedValues["sudo"] ? this.state.mixedValues["sudo"] : "" }
                            defaultValue     = { this.props.item[ "sudo" ] }
                            onChange         = { this.editHandleValueChange.bind( null, "sudo" ) }
                            key              = { "sudo" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["sudo"]) ? "editor-was-modified" : "" }
                            ref              = "sudo"
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* password_disabled */}
                <TWBS.Input type             = "checkbox"
                            label            = { "password_disabled" }
                            checked          = { this.state.mixedValues["password_disabled"] }
                            value            = { this.state.mixedValues["password_disabled"] ? this.state.mixedValues["password_disabled"] : "" }
                            defaultValue     = { this.props.item[ "password_disabled" ] }
                            onChange         = { this.editHandleValueChange.bind( null, "password_disabled" ) }
                            key              = { "password_disabled" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["password_disabled"]) ? "editor-was-modified" : "" }
                            ref              = "password_disabled"
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
                {/* logged-in */}
                <TWBS.Input type             = "checkbox"
                            checked          = { this.state.mixedValues["logged-in"] }
                            label            = { "logged-in" }
                            value            = { this.state.mixedValues["logged-in"] ? this.state.mixedValues["logged-in"] : "" }
                            defaultValue     = { this.props.item[ "logged-in" ] }
                            onChange         = { this.editHandleValueChange.bind( null, "logged-in" ) }
                            key              = { "logged-in" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["logged-in"]) ? "editor-was-modified" : "" }
                            ref              = "logged-in"
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8" />
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

          {inputForm}

          {/* Save and Cancel Buttons - Bottom */}
          { editButtons }
        </TWBS.Grid>
      );
    }

});


// CONTROLLER-VIEW
const UserItem = React.createClass({

    propTypes: {
        viewData : React.PropTypes.object.isRequired
    }

  , mixins: [ routerShim, clientStatus ]

  , getInitialState: function () {
      return {
          targetUser  : this.getUserFromStore()
        , currentMode : "view"
        , activeRoute : this.getDynamicRoute()
      };
    }

  , componentDidUpdate: function( prevProps, prevState ) {
      var activeRoute = this.getDynamicRoute();

      if ( activeRoute !== prevState.activeRoute ) {
        this.setState({
            targetUser  : this.getUserFromStore()
          , currentMode : "view"
          , activeRoute : activeRoute
        });
      }
    }

  , componentDidMount: function () {
      UsersStore.addChangeListener( this.updateUserInState );
    }

  , componentWillUnmount: function () {
      UsersStore.removeChangeListener( this.updateUserInState );
    }

  , getUserFromStore: function () {
      return UsersStore.findUserByKeyValue( this.props.viewData.format["selectionKey"], this.getDynamicRoute() );
    }

  , updateUserInState: function () {
      this.setState({ targetUser: this.getUserFromStore() });
    }

  , handleViewChange: function ( nextMode, event ) {
      this.setState({ currentMode: nextMode });
    }

  , render: function () {
      var DisplayComponent = null;
      var processingText   = "";

      if ( this.state.SESSION_AUTHENTICATED && this.state.targetUser ) {

        // PROCESSING OVERLAY
        if ( UsersStore.isLocalTaskPending( this.state.targetUser["id"] ) ) {
          processingText = "Saving changes to '" + this.state.targetUser[ this.props.viewData.format["primaryKey"] ] + "'";
        } else if ( UsersStore.isUserUpdatePending( this.state.targetUser["id"] ) ) {
          processingText = "User '" + this.state.targetUser[ this.props.viewData.format["primaryKey"] ] + "' was updated remotely.";
        }

        // DISPLAY COMPONENT
        var childProps = {
            handleViewChange : this.handleViewChange
          , item             : this.state.targetUser
          , viewData         : this.props.viewData
        };

        switch ( this.state.currentMode ) {
          default:
          case "view":
            DisplayComponent = <UserView { ...childProps } />;
            break;

          case "edit":
            DisplayComponent = <UserEdit { ...childProps } />;
            break;
        }
      }

      return (
        <div className="viewer-item-info">

          {/* Overlay to block interaction while tasks or updates are processing */}
          <editorUtil.updateOverlay updateString={ processingText } />

          { DisplayComponent }

        </div>
      );
    }

});

export default UserItem;
