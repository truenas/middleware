// User Item Template
// ==================
// Handles the viewing and editing of individual user items. Shows a non-editable
// overview of the user account, and mode-switches to a more standard editor
// panel. User is set by providing a route parameter.

"use strict";

var _      = require("lodash");
var React  = require("react");
var TWBS   = require("react-bootstrap");
var Router = require("react-router");

var viewerUtil  = require("../../../components/Viewer/viewerUtil");
var editorUtil  = require("../../../components/Viewer/Editor/editorUtil");
var activeRoute = require("../../../components/Viewer/mixins/activeRoute");

var UsersMiddleware = require("../../../middleware/UsersMiddleware");
var UsersStore      = require("../../../stores/UsersStore");

var GroupsMiddleware = require("../../../middleware/GroupsMiddleware");
var GroupsStore      = require("../../../stores/GroupsStore");

// OVERVIEW PANE
var UserView = React.createClass({

    propTypes: {
      item: React.PropTypes.object.isRequired
    }

  , getPrimaryGroup: function(groupID) {
    return GroupsStore.getGroup(groupID).name;
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
                                 entry  = { this.getPrimaryGroup(this.props.item["group"]) } />
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

    propTypes: {
      item: React.PropTypes.object.isRequired
    }

  , getInitialState: function() {
      var remoteState = this.setRemoteState( this.props );

      return {
          locallyModifiedValues  : {}
        , remotelyModifiedValues : {}
        , remoteState            : remoteState
        , mixedValues            : this.props.item
        , lastSentValues         : {}
      };
    }

    // Remote state is set at load time and reset upon successful changes.
  , setRemoteState: function ( incomingProps ) {
      var nextRemoteState = {};

      _.forEach( incomingProps["item"], function( value, key ) {
        var itemKey = _.find(incomingProps["dataKeys"], function ( item ) {
          return item.key === key;
        }.bind(this) );
        if (!itemKey) {
          // Do not accept unknown properties from the Middleware.
          // TODO: If we want to accept arbitrary properies, we will need more
          // sophisticated handling here.
          console.error("Received an unknown property \"" + key + "\" from the Middleware Server.");
          console.error(this.props.item);
        } else {
          nextRemoteState[ key ] = this.props.item[ key ];
        }
      }.bind(this) );

      if (!nextRemoteState) {
        console.error("Remote State could not be created! Check the incoming props:");
        console.error(incomingProps);
      }

      return nextRemoteState;
  }

  , componentWillReceiveProps: function( nextProps ) {
      var newRemoteModified  = {};
      var newLocallyModified = {};
      var oldLocallyModified = this.state.locallyModifiedValues;

      // remotelyModifiedValues represents everything that's changed remotely
      // since the view was opened. This is the difference between the newly arriving
      // props and the initial ones. Read-only and unknown values are ignored.
      // TODO: Make this the difference between the initial state OR the last time
      // the local administrator saved successfully. Currently this will treat
      // successfully submitted local changes as remote changes.
      _.forEach( nextProps.item, function( value, key ) {
        var itemKey = _.find(this.props["dataKeys"], function ( item ) {
          return item.key === key;
        }.bind(this) );
        if (!itemKey) {
          // Do not accept unknown properties from the Middleware.
          // TODO: If we want to accept arbitrary properies, we will need more
          // sophisticated handling here.
          console.error("Received an unknown property \"" + key + "\" from the Middleware Server.");
          console.error(nextProps.item);
        } else if ( !_.isEqual( this.state.remoteState[ key ], nextProps.item[ key ] ) && itemKey.mutable ) {
          newRemoteModified[ key ] = nextProps.item[ key ];
        }
      }.bind(this) );
      // locallyModifiedValues represents the difference between the remote state
      // of the item and the edits in progress. Read-only values MUST NOT be included.
      _.forEach( this.props.item, function( value, key ) {
        var itemKey = _.find(this.props["dataKeys"], function ( item ) {
          return item.key === key;
        }.bind(this) );
        if ( !_.isEqual( nextProps.item[ key ], value ) && itemKey.mutable ) {
          newLocallyModified[ key ] = value;
        }
      }.bind(this) );

      // When a remote value becomes identical to an edit in progress, that value
      // should no longer be treated as having been changed locally. To this end,
      // we compare newly arrived properties to the old locally modified ones, and
      // remove the matching values from newLocallyModified.
      // TODO: Make the view give some visual indication which values have been
      // overriden by remote ones.
      _.forEach( oldLocallyModified, function( value, key ) {
        if ( _.isEqual( value, nextProps.key ) ) {
          delete newLocallyModified[ key ];
        }
      }.bind(this) );

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
              remoteState : this.setRemoteState(nextProps)
          });
      }

      // It is also necessary to set remoteState after accepting new changes
      // from a remote change.

      this.setState({
          locallyModifiedValues  : newLocallyModified
        , remotelyModifiedValues : newRemoteModified
      });
    }

  , handleValueChange: function( key, event ) {
      var newValues  = this.state.locallyModifiedValues;
      var inputValue;

      // Use different logic to interpret input from different kinds of fields.
      // TODO: Cover every field in use with different cases as needed.
      switch (event.target.type) {

        case "checkbox" :
          inputValue = event.target.checked;
          break;

        default:
          inputValue = event.target.value;
          break;
      }

      // We don't want to submit non-changed data to the middleware, and it's
      // easy for data to appear "changed", even if it's the same. Here, we
      // check to make sure that the input value we've just receieved isn't the
      // same as what the last payload from the middleware shows as the value
      // for the same key. If it is, we `delete` the key from our temp object
      // and update state.
      if ( _.isEqual( this.props.item[ key ], inputValue ) ) {
        delete newValues[ key ];
      } else {
        newValues[ key ] = inputValue;
      }

      // mixedValues functions as a clone of the original item passed down in
      // props, and is modified with the values that have been changed by the
      // user. This allows the display components to have access to the
      // "canonically" correct item, merged with the un-changed values.
      this.setState({
          locallyModifiedValues : newValues
        , mixedValues    : _.assign( _.cloneDeep( this.props.item ), newValues )
      });
    }

  , submitUserUpdate: function() {
      var valuesToSend = {};

      // Make sure nothing read-only made it in somehow.
      _.forEach( this.state.locallyModifiedValues, function( value, key ) {
        var itemKey = _.find(this.props["dataKeys"], function ( item ) {
          return item.key === key;
        }.bind(this) );
        if ( itemKey.mutable ) {
          valuesToSend[ key ] = value;
        } else {
          console.error("USERS: Attempted to submit a change to a read-only property.");
          console.error(this.state.locallyModifiedValues[value]);
        }
      }.bind(this) );

      if (valuesToSend){
        // Only bother to submit an update if there is anything to update.
        UsersMiddleware.updateUser( this.props.item["id"], valuesToSend );
        // Save a record of the last changes we sent.
        this.setState({
            lastSentValues : valuesToSend
        });
      } else {
          console.warn("Attempted to send a User update with no valid fields.");
      }

    }

  , render: function() {
      var builtInUserAlert  = null;
      var editButtons       = null;

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
            <TWBS.Button className = "pull-right"
                         onClick   = { this.props.handleViewChange.bind(null, "view") }
                         bsStyle   = "default" >{"Cancel"}</TWBS.Button>
            <TWBS.Button className = "pull-right"
                         disabled  = { _.isEmpty( this.state.locallyModifiedValues ) ? true : false }
                         onClick   = { this.submitUserUpdate }
                         bsStyle   = "info" >{"Save Changes"}</TWBS.Button>
        </TWBS.ButtonToolbar>;

      return (
        <TWBS.Grid fluid>
          {/* Save and Cancel Buttons - Top */}
          { editButtons }

          {/* Shows a warning if the user account is built in */}
          { builtInUserAlert }

          <form className="form-horizontal">
            {
              this.props["dataKeys"].map( function( displayKeys, index ) {
                return editorUtil.identifyAndCreateFormElement(
                          // value
                          this.state.mixedValues[ displayKeys["key"] ]
                          // displayKeys
                        , displayKeys
                          // changeHandler
                        , this.handleValueChange
                          // key
                        , index
                          // wasModified
                        , _.has( this.state.locallyModifiedValues, displayKeys["key"] )
                       );
              }.bind( this ) )
            }
          </form>

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

  , mixins: [ Router.State, activeRoute ]

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

      // PROCESSING OVERLAY
      if ( UsersStore.isLocalTaskPending( this.state.targetUser["id"] ) ) {
        processingText = "Saving changes to '" + this.state.targetUser[ this.props.viewData.format["primaryKey"] ] + "'";
      } else if ( UsersStore.isUserUpdatePending( this.state.targetUser["id"] ) ) {
        processingText = "User '" + this.state.targetUser[ this.props.viewData.format["primaryKey"] ] + "' was updated remotely.";
      }

      // DISPLAY COMPONENT
      switch ( this.state.currentMode ) {
        default:
        case "view":
          DisplayComponent = UserView;
          break;

        case "edit":
          DisplayComponent = UserEdit;
          break;
      }

      return (
        <div className="viewer-item-info">

          {/* Overlay to block interaction while tasks or updates are processing */}
          <editorUtil.updateOverlay updateString={ processingText } />

          <DisplayComponent handleViewChange = { this.handleViewChange }
                            item             = { this.state.targetUser }
                            dataKeys         = { this.props.viewData.format["dataKeys"] } />

        </div>
      );
    }

});

module.exports = UserItem;
