/** @jsx React.DOM */

// Editor Utilities
// ================
// A group of utility functions designed to make the creation of Editor/Viewer
// templates simpler and more straightforward.

"use strict";

var React = require("react");
var TWBS  = require("react-bootstrap");

var Throbber = require("../../common/Throbber");

var editorUtil = exports;

editorUtil.identifyAndCreateFormElement = function ( value, displayKeys, changeHandler, key, wasModified ) {
  var formElement;

  switch ( displayKeys["formElement"] ) {
    case "input":
      formElement = editorUtil.createInput( value, displayKeys, changeHandler, key, wasModified );
      break;

    case "textarea":
      formElement = editorUtil.createTextarea( value, displayKeys, changeHandler, key, wasModified );
      break;

    case "checkbox":
      formElement = editorUtil.createCheckbox( value, displayKeys, changeHandler, key, wasModified );
      break;

    default:
      if ( displayKeys["formElement"] ) {
        console.warn( displayKeys["formElement"] + " for value '" + value + "' is of unrecognized type" );
      } else {
        console.warn( value + " didn't have a defined formElement property" );
      }
      formElement = editorUtil.createInput( value, displayKeys, changeHandler, key, wasModified );
      break;
  }

  return formElement;

};

editorUtil.createInput = function ( value, displayKeys, changeHandler, key, wasModified ) {

  return(
    <TWBS.Input type        = "text"
           label            = { displayKeys["name"] }
           value            = { value }
           onChange         = { changeHandler.bind( null, displayKeys["key"] ) }
           key              = { key }
           groupClassName   = { wasModified ? "editor-was-modified" : "" }
           labelClassName   = "col-xs-4"
           wrapperClassName = "col-xs-8" />
  );
};

editorUtil.createTextarea = function ( value, displayKeys, changeHandler, key, wasModified ) {
  return(
    <TWBS.Input type        = "textarea"
           label            = { displayKeys["name"] }
           value            = { value }
           onChange         = { changeHandler.bind( null, displayKeys["key"] ) }
           key              = { key }
           groupClassName   = { wasModified ? "editor-was-modified" : "" }
           labelClassName   = "col-xs-4"
           wrapperClassName = "col-xs-8" />
  );
};

editorUtil.updateOverlay = React.createClass({

    propTypes: {
        updateString  : React.PropTypes.string
      , throbberStyle : React.PropTypes.string
      , animDuration  : React.PropTypes.number
      , animDelay     : React.PropTypes.number
    }

  , getDefaultProps: function() {
      return {
          animDuration : 250
        , animDelay    : 600
      };
    }

  , getInitialState: function() {
      return { animating: false };
    }

  , componentDidUpdate: function( prevProps, prevState ) {
      // Using !! performs boolean type coercion
      var oldBool = !!prevProps.updateString;
      var newBool = !!this.props.updateString;

      // Functions as logical XOR to detect disparity between length states
      if ( oldBool !== newBool ) {
        this.updateOverlayVisibility( newBool );
      }
    }

  , updateOverlayVisibility: function( newBool ) {
      // If the new property had length, and the old one didn't (determined by
      // XOR), we know that we're going from nothing to soemthing, so we fadein.
      // The same holds true in the opposite case, causing a fadeout.
      if ( newBool ) {
        Velocity( this.refs["update-overlay"].getDOMNode()
                , "fadeIn"
                , {
                      duration : this.props.animDuration
                    , display  : "flex"
                  }
                );
      } else {
        Velocity( this.refs["update-overlay"].getDOMNode()
                , "fadeOut"
                , {
                      duration : this.props.animDuration
                    , delay    : this.props.animDelay
                  }
                );
      }

      this.setState({ animating: true });

      this.animTimeout = setTimeout( function() {
          this.setState({ animating: false });
        }.bind(this)
        , this.props.animDuration + this.props.animDelay + 250
      );
    }


  , render: function() {
      var overlay = null;

      // Using !! performs boolean type coercion
      if ( this.props.updateString.length || this.state.animating ) {
        overlay = (
          <div className = "overlay overlay-light editor-update-overlay"
               ref       = "update-overlay"
               style     = {{ opacity: 0 }} >
            <div>
              <h3>{ this.props.updateString || "Done." }</h3>
              <Throbber bsStyle={ this.props.throbberStyle || "primary" } />
            </div>
          </div>
        );
      }

      return overlay;
    }

});