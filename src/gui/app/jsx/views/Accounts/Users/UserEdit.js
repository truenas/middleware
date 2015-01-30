/** @jsx React.DOM */

// User Edit Template
// ==================


"use strict";

var _          = require("lodash");
var React      = require("react");
var TWBS       = require("react-bootstrap");

var editorUtil = require("../../../components/Viewer/Editor/editorUtil");
var Throbber   = require("../../../components/common/Throbber");

var UsersMiddleware = require("../../../middleware/UsersMiddleware");
var UsersStore      = require("../../../stores/UsersStore");

var UserEdit = React.createClass({

    propTypes: {
      item: React.PropTypes.object.isRequired
    }

  , getUpdateStatus: function() {
      return {
          pendingTaskCompletion : false
        , pendingUpdateOnServer : UsersStore.isUserUpdatePending( this.props.item["id"] )
      };
    }

  , getInitialState: function() {
      return _.assign({
            modifiedValues        : {}
          , mixedValues           : this.props.item
        }
        , this.getUpdateStatus()
      );
    }

  , componentDidMount: function() {
      UsersStore.addChangeListener( this.handleUsersChange );
    }

  , componentWillUnmount: function() {
      UsersStore.removeChangeListener( this.handleUsersChange );
    }

  , handleUsersChange: function() {
      this.setState( this.getUpdateStatus() );
    }

  , handleValueChange: function( key, event ) {
      var newValues  = this.state.modifiedValues;
      var inputValue = event.target.value;

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

      var processingOverlay = null;
      var builtInUserAlert  = null;
      var editButtons       = null;

      if ( this.state.pendingUpdateOnServer || this.state.pendingTaskCompletion ) {
        var processingText = null;

        if ( this.state.pendingUpdateOnServer ) {
          processingText = <h3>{"Saving changes to " + this.state.mixedValues[ this.props.formatData["primaryKey"] ] }</h3>;
        }

        if ( this.state.pendingTaskCompletion ) {
          processingText = <h3>{ "Syncing " + this.state.mixedValues[ this.props.formatData["primaryKey"] ] }</h3>;
        }

        processingOverlay = (
          <div className = "overlay overlay-light editor-update-overlay"
               ref       = "saving-overlay">
            <div>
              { processingText }
              <Throbber bsStyle="primary" />
            </div>
          </div>
        );
      }

      if ( this.props.item["builtin"] ) {
        builtInUserAlert = (
          <TWBS.Row>
            <TWBS.Col xs={12}>
              <TWBS.Alert bsStyle   = "warning"
                          className = "text-center">
                <b>{"You should only edit a system user account if you know exactly what you're doing."}</b>
              </TWBS.Alert>
            </TWBS.Col>
          </TWBS.Row>
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
        <div className="viewer-item-info">

          {/* Overlay to block interaction while tasks or updates are processing */}
          { processingOverlay }

          <TWBS.Grid fluid>
            {/* Save and Cancel Buttons - Top */}
            { editButtons }

            {/* Shows a warning if the user account is built in */}
            { builtInUserAlert }

            <form className="form-horizontal">
              {
                this.props.formatData["dataKeys"].map( function( displayKeys, index ) {
                  return editorUtil.identifyAndCreateFormElement(
                           this.state.mixedValues[ displayKeys["key"] ],
                           displayKeys,
                           this.handleValueChange
                         );
                }.bind( this ) )
              }
            </form>

            {/* Save and Cancel Buttons - Bottom */}
            { editButtons }
          </TWBS.Grid>
        </div>
      );
    }

});

module.exports = UserEdit;
