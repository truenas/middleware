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
                                 entry  = { this.props.item["group"] } />
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
      return {
          modifiedValues : {}
        , mixedValues    : this.props.item
      };
    }

  , componentWillReceiveProps: function( nextProps ) {
      var newModified = {};
      var oldModified = _.cloneDeep( this.state.modifiedValues );

      // Any remote changes will cause the current property to be shown as
      // having been "modified", signalling to the user that saving it will
      // have the effect of changing that value
      _.forEach( nextProps.item, function( value, key ) {
        if ( this.props.item[ key ] !== value ) {
          newModified[ key ] = this.props.item[ key ];
        }
      }.bind(this) );

      // Any remote changes which are the same as locally modified changes should
      // cause the local modifications to be ignored.
      _.forEach( oldModified, function( value, key ) {
        if ( this.props.item[ key ] === value ) {
          delete oldModified[ key ];
        }
      }.bind(this) );

      this.setState({
          modifiedValues : _.assign( oldModified, newModified )
      });
    }

  , handleValueChange: function( key, event ) {
      var newValues  = this.state.modifiedValues;
      var inputValue;
      if (event.target.type === "checkbox") {
        inputValue = event.target.checked;
      } else {
        inputValue = event.target.value;
      }
      // We don't want to submit non-changed data to the middleware, and it's
      // easy for data to appear "changed", even if it's the same. Here, we
      // check to make sure that the input value we've just receieved isn't the
      // same as what the last payload from the middleware shows as the value
      // for the same key. If it is, we `delete` the key from our temp object
      // and update state.
      if ( this.props.item[ key ] === inputValue ) {
        delete newValues[ key ];
      } else {
        newValues[ key ] = inputValue;
      }

      // mixedValues functions as a clone of the original item passed down in
      // props, and is modified with the values that have been changed by the
      // user. This allows the display components to have access to the
      // "canonically" correct item, merged with the un-changed values.
      this.setState({
          modifiedValues : newValues
        , mixedValues    : _.assign( _.cloneDeep( this.props.item ), newValues )
      });
    }

  , submitUserUpdate: function() {
      UsersMiddleware.updateUser( this.props.item["id"], this.state.modifiedValues );
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
                         disabled  = { _.isEmpty( this.state.modifiedValues ) ? true : false }
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
                        , _.has( this.state.modifiedValues, displayKeys["key"] )
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
