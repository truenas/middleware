// User Item Template
// ==================
// Handles the viewing and editing of individual user items. Shows a non-editable
// overview of the user account, and mode-switches to a more standard editor
// panel. User is set by providing a route parameter.

"use strict";

var _      = require("lodash");
var React  = require("react");
var TWBS   = require("react-bootstrap");

var activeRoute  = require("../../../components/mixins/activeRoute");
var clientStatus = require("../../../components/mixins/clientStatus");

var viewerUtil  = require("../../../components/Viewer/viewerUtil");
var editorUtil  = require("../../../components/Viewer/Editor/editorUtil");

var UsersMiddleware = require("../../../middleware/UsersMiddleware");
var UsersStore      = require("../../../stores/UsersStore");

var GroupsStore      = require("../../../stores/GroupsStore");

var inputHelpers = require("../../../components/mixins/inputHelpers");
var userMixins   = require("../../../components/mixins/userMixins");
var viewerCommon = require("../../../components/mixins/viewerCommon");

// OVERVIEW PANE
var UserView = React.createClass({

    propTypes: {
      item: React.PropTypes.object.isRequired
    }

  , getGroupName: function(groupID) {
      var group = GroupsStore.getGroup(groupID);

      if ( group ) {
        return group.name;
      } else {
        console.warn("Group " + groupID + " not found.");
        return null;
      }
    }

  , render: function() {
      var builtInUserAlert = null;
      var editButton       = null;

      if ( this.props.item["builtin"] ) {
        builtInUserAlert = (
          <TWBS.Alert bsStyle   = "info"
                      className = "text-center">
            <b>{"This is a built-in FreeNAS user account."}</b>
          </TWBS.Alert>
        );
      }

      editButton = (
        <TWBS.Row>
          <TWBS.Col xs={12}>
            <TWBS.Button className = "pull-right"
                         onClick   = { this.props.handleViewChange.bind(null, "edit") }
                         bsStyle   = "info" >{"Edit User"}</TWBS.Button>
          </TWBS.Col>
        </TWBS.Row>
      );

      return (
        <TWBS.Grid fluid>
          {/* "Edit User" Button - Top */}
          { editButton }

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
                                 entry  = { this.props.item["locked"] } />
            <viewerUtil.DataCell title  = { "Sudo Access" }
                                 colNum = { 3 }
                                 entry  = { this.props.item["sudo"] } />
            <viewerUtil.DataCell title  = { "Password Disabled" }
                                 colNum = { 3 }
                                 entry  = { this.props.item["password_disabled"] } />
            <viewerUtil.DataCell title  = { "Logged In" }
                                 colNum = { 3 }
                                 entry  = { this.props.item["logged-in"] } />
            <viewerUtil.DataCell title  = { "Home Directory" }
                                 colNum = { 3 }
                                 entry  = { this.props.item["home"] } />
            <viewerUtil.DataCell title  = { "email" }
                                 colNum = { 3 }
                                 entry  = { this.props.item["email"] } />
          </TWBS.Row>

          {/* "Edit User" Button - Bottom */}
          { editButton }

        </TWBS.Grid>
      );
    }

});


// EDITOR PANE
var UserEdit = React.createClass({

    mixins: [  inputHelpers
             , userMixins
             , viewerCommon ]

  , contextTypes: {
        router: React.PropTypes.func
    }

  , propTypes: {
        item     : React.PropTypes.object.isRequired
      , viewData : React.PropTypes.object.isRequired
      }

  , getInitialState: function() {
      var remoteState = this.setRemoteState( this.props );

      return {
          locallyModifiedValues  : {}
        , remotelyModifiedValues : {}
        , remoteState            : remoteState
        , mixedValues            : this.props.item
        , lastSentValues         : {}
        , dataKeys               : this.props.viewData["format"]["dataKeys"]
      };
    }

    // Remote state is set at load time and reset upon successful changes
  , setRemoteState: function ( incomingProps ) {
      var dataKeys = incomingProps.viewData["format"]["dataKeys"];
      var nextRemoteState = this.removeReadOnlyFields(incomingProps.item, dataKeys);

      if (_.isEmpty(nextRemoteState)) {
        console.warn("Remote State could not be created! Check the incoming props:");
        console.warn(incomingProps);
      }

      // TODO: What exactly should be returned if setting the remote state is
      // going to fail?
      return nextRemoteState;
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

    // TODO: Turn this into a mixin so it can be used by any edit view.
  , handleValueChange: function( key, event ) {
      var newLocallyModified = this.state.locallyModifiedValues;

      var dataKey = _.find(this.state.dataKeys, function (dataKey) {
        return (dataKey.key === key);
      }, this);

      var inputValue = this.processFormInput( event, dataKey );

      // We don't want to submit non-changed data to the middleware, and it's
      // easy for data to appear "changed", even if it's the same. Here, we
      // check to make sure that the input value we've just receieved isn't the
      // same as what the last payload from the middleware shows as the value
      // for the same key. If it is, we `delete` the key from our temp object
      // and update state.
      if ( _.isEqual( this.state.remoteState[ key ], inputValue ) ) {
        delete newLocallyModified[ key ];
      } else {
        newLocallyModified[ key ] = inputValue;
      }

      // mixedValues functions as a clone of the original item passed down in
      // props, and is modified with the values that have been changed by the
      // user. This allows the display components to have access to the
      // "canonically" correct item, merged with the un-changed values.
      this.setState({
          locallyModifiedValues : newLocallyModified
        , mixedValues           : _.assign( _.cloneDeep( this.props.item ), newLocallyModified )
      });
    }

    // TODO: Validate that input values are legitimate for their field. For example,
    // id should be a number.
  , submitUserUpdate: function() {
      var valuesToSend = {};

      // Make sure nothing read-only made it in somehow.
      valuesToSend = this.removeReadOnlyFields(this.state.locallyModifiedValues, this.state.dataKeys);

      // Only bother to submit an update if there is anything to update.
      if (!_.isEmpty( valuesToSend ) ){
        UsersMiddleware.updateUser( this.props.item["id"], valuesToSend, this.submissionRedirect(valuesToSend) );
        // Save a record of the last changes we sent.
        this.setState({
            lastSentValues : valuesToSend
        });
      } else {
          console.warn("Attempted to send a User update with no valid fields.");
      }

    }

      // TODO: Put it in an mixin? It requires a lot of view-specific info,
      // but if more such things become mixins themselves, it would probably work.
    , submissionRedirect: function( valuesToSend ) {
        var params = {};
        var nextUser;

        if (valuesToSend[ "username" ]) {
          nextUser = valuesToSend[ "username" ];
          params[this.props.viewData.routing[ "param" ] ] = nextUser;
          this.context.router.transitionTo( "users-editor", params );
        } else {
          this.props.handleViewChange("view");
        }
    }

    , deleteUser: function(){
        UsersMiddleware.deleteUser(this.props.item["id"], this.returnToViewerRoot() );
    }

    // TODO: Currently this section just arbitrarily handles every property the
    // middleware sends in the order the browser sends it. This should be updated
    // to have a deliberate design.
    // TODO: Add alerts when a remote administrator has changed items that the
    // local administrator is also working on.
  , render: function() {
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
                            value            = { this.state.mixedValues["id"] ? this.state.mixedValues["id"] : "" }
                            onChange         = { this.handleValueChange.bind( null, "id" ) }
                            key              = { "id" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["id"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            disabled         = { !this.isMutable( "id", this.state.dataKeys) } />
                {/* username */}
                <TWBS.Input type             = "text"
                            label            = { "User Name" }
                            value            = { this.state.mixedValues["username"] ? this.state.mixedValues["username"] : "" }
                            onChange         = { this.handleValueChange.bind( null, "username" ) }
                            key              = { "username" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["username"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            disabled         = { !this.isMutable( "username", this.state.dataKeys) } />
                {/* full_name*/}
                <TWBS.Input type             = "text"
                            label            = { "Full Name" }
                            value            = { this.state.mixedValues["full_name"] ? this.state.mixedValues["full_name"] : "" }
                            onChange         = { this.handleValueChange.bind( null, "full_name" ) }
                            key              = { "full_name" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["full_name"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            disabled         = { !this.isMutable( "full_name", this.state.dataKeys) } />
                {/* email */}
                  <TWBS.Input type             = "text"
                            label            = { "email" }
                            value            = { this.state.mixedValues["email"] ? this.state.mixedValues["email"] : "" }
                            onChange         = { this.handleValueChange.bind( null, "email" ) }
                            key              = { "email" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["email"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            disabled         = { !this.isMutable( "email", this.state.dataKeys) } />
                {/* shell */}
                <TWBS.Input type             = "select"
                            label            = { "Shell" }
                            value            = { this.state.mixedValues["shell"] ? this.state.mixedValues["shell"] : "" }
                            onChange         = { this.handleValueChange.bind( null, "shell" ) }
                            key              = { "shell" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["shell"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            disabled         = { !this.isMutable( "shell", this.state.dataKeys) }>
                            { this.generateOptionsList( this.state.shells ) }
                </TWBS.Input>
                {/* sshpubkey */}
                <TWBS.Input type             = "textarea"
                            label            = { "Public Key" }
                            value            = { this.state.mixedValues["sshpubkey"] ? this.state.mixedValues["sshpubkey"] : "" }
                            onChange         = { this.handleValueChange.bind( null, "sshpubkey" ) }
                            key              = { "sshpubkey" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["sshpubkey"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            disabled         = { !this.isMutable( "sshpubkey", this.state.dataKeys) }>
                </TWBS.Input>
              </TWBS.Col>
              <TWBS.Col xs = {4}>
                {/* locked */}
                <TWBS.Input type             = "checkbox"
                            checked          = { this.state.mixedValues["locked"] }
                            label            = { "Locked" }
                            value            = { this.state.mixedValues["locked"] ? this.state.mixedValues["locked"] : "" }
                            onChange         = { this.handleValueChange.bind( null, "locked" ) }
                            key              = { "locked" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["locked"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            disabled         = { !this.isMutable( "locked", this.state.dataKeys) } />
                {/* sudo */}
                <TWBS.Input type             = "checkbox"
                            checked          = { this.state.mixedValues["sudo"] }
                            label            = { "sudo" }
                            value            = { this.state.mixedValues["sudo"] ? this.state.mixedValues["sudo"] : "" }
                            onChange         = { this.handleValueChange.bind( null, "sudo" ) }
                            key              = { "sudo" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["sudo"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            disabled         = { !this.isMutable( "sudo", this.state.dataKeys) } />
                {/* password_disabled */}
                <TWBS.Input type             = "checkbox"
                            label            = { "password_disabled" }
                            checked          = { this.state.mixedValues["password_disabled"] }
                            value            = { this.state.mixedValues["password_disabled"] ? this.state.mixedValues["password_disabled"] : "" }
                            onChange         = { this.handleValueChange.bind( null, "password_disabled" ) }
                            key              = { "password_disabled" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["password_disabled"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            disabled         = { !this.isMutable( "password_disabled", this.state.dataKeys) } />
                {/* logged-in */}
                <TWBS.Input type             = "checkbox"
                            checked          = { this.state.mixedValues["logged-in"] }
                            label            = { "logged-in" }
                            value            = { this.state.mixedValues["logged-in"] ? this.state.mixedValues["logged-in"] : "" }
                            onChange         = { this.handleValueChange.bind( null, "logged-in" ) }
                            key              = { "logged-in" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["logged-in"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            disabled         = { !this.isMutable( "logged-in", this.state.dataKeys ) } />
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
var UserItem = React.createClass({

    propTypes: {
        viewData : React.PropTypes.object.isRequired
    }

  , mixins: [ activeRoute, clientStatus ]

  , getInitialState: function() {
      return {
          targetUser  : this.getUserFromStore()
        , currentMode : "view"
        , activeRoute : this.getActiveRoute()
      };
    }

  , componentDidUpdate: function( prevProps, prevState ) {
      var activeRoute = this.getActiveRoute();

      if ( activeRoute !== prevState.activeRoute ) {
        this.setState({
            targetUser  : this.getUserFromStore()
          , currentMode : "view"
          , activeRoute : activeRoute
        });
      }
    }

  , componentDidMount: function() {
      UsersStore.addChangeListener( this.updateUserInState );
    }

  , componentWillUnmount: function() {
      UsersStore.removeChangeListener( this.updateUserInState );
    }

  , getUserFromStore: function() {
      return UsersStore.findUserByKeyValue( this.props.viewData.format["selectionKey"], this.getActiveRoute() );
    }

  , updateUserInState: function() {
      this.setState({ targetUser: this.getUserFromStore() });
    }

  , handleViewChange: function ( nextMode, event ) {
      this.setState({ currentMode: nextMode });
    }

  , render: function() {
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

module.exports = UserItem;
