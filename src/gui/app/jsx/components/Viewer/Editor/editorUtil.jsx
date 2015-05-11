// Editor Utilities
// ================
// A group of utility functions designed to make the creation of Editor/Viewer
// templates simpler and more straightforward.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import Throbber from "../../common/Throbber";

var editorUtil = exports;

editorUtil.updateOverlay = React.createClass({

    propTypes: {
        updateString  : React.PropTypes.string
      , throbberStyle : React.PropTypes.string
      , animDuration  : React.PropTypes.number
      , animDelay     : React.PropTypes.number
    }

  , getDefaultProps: function () {
      return {
          animDuration : 250
        , animDelay    : 600
      };
    }

  , getInitialState: function () {
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


  , render: function () {
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