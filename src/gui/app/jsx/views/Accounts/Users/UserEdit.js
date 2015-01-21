/** @jsx React.DOM */

// User Edit Template
// ==================


"use strict";

var _          = require("lodash");
var React      = require("react");
var TWBS       = require("react-bootstrap");

// var viewerUtil = require("../../../components/Viewer/viewerUtil");
var editorUtil = require("../../../components/Viewer/Editor/editorUtil");

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

  , render: function() {

      var builtInUserAlert = null;

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

      var editButtons =
        <TWBS.ButtonToolbar>
            <TWBS.Button className = "pull-right"
                         onClick   = { this.props.handleViewChange.bind(null, "view") }
                         bsStyle   = "default" >{"Cancel"}</TWBS.Button>
            <TWBS.Button className = "pull-right"
                         disabled  = { _.isEmpty( this.state.modifiedValues ) ? true : false }
                         bsStyle   = "info" >{"Save Changes"}</TWBS.Button>
        </TWBS.ButtonToolbar>;

      return (
        <TWBS.Grid fluid className="viewer-item-info">
          {/* Save and Cancel Buttons - Top */}
          { editButtons }

          {/* Shows a warning if the user account is built in */}
          { builtInUserAlert }

          <form className="form-horizontal">
            { this.props.formatData["dataKeys"].map( function( displayKeys, index ) {
                return editorUtil.identifyAndCreateFormElement( this.state.mixedValues[ displayKeys["key"] ], displayKeys, this.handleValueChange );
              }.bind( this ) )
            }
          </form>

          {/* Save and Cancel Buttons - Bottom */}
          { editButtons }

        </TWBS.Grid>
      );
    }

});

module.exports = UserEdit;
