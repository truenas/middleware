/** @jsx React.DOM */

// Viewer Utilities
// ================
// A group of utility functions for the Viewer and associated content.

"use strict";

var React = require("react");

var viewerUtil = exports;

viewerUtil.getPastelColor = function( seed ) {
  var r, g, b;

  var h = ( ( 137.5 * seed ) % 360 ) / 360 ;
  var s = 0.25;
  var v = 0.65;

  var i = Math.floor(h * 6);
  var f = h * 6 - i;
  var p = v * (1 - s);
  var q = v * (1 - f * s);
  var t = v * (1 - (1 - f) * s);

  switch(i % 6) {
      case 0: r = v, g = t, b = p; break;
      case 1: r = q, g = v, b = p; break;
      case 2: r = p, g = v, b = t; break;
      case 3: r = p, g = q, b = v; break;
      case 4: r = t, g = p, b = v; break;
      case 5: r = v, g = p, b = q; break;
  }

  return [
      Math.round( r * 255 )
    , Math.round( g * 255 )
    , Math.round( b * 255 )
  ];
};

viewerUtil.ItemIcon = React.createClass({

    propTypes: {
        iconImage       : React.PropTypes.string
      , size            : React.PropTypes.number
      , fontSize        : React.PropTypes.number
      , primaryString   : React.PropTypes.string
      , fallbackString  : React.PropTypes.string.isRequired
      , seedNumber      : React.PropTypes.number.isRequired
    }

  , componentWillMount: function() {
      this.setFallbackIcon( this.props );
  }

  , componentWillReceiveProps: function( nextProps ) {
      this.setFallbackIcon( nextProps );
  }

  , setFallbackIcon: function( props ) {
      // If there's a profile picture we can use, don't bother with setup
      if ( props.iconImage ) {
        return;
      } else {
        var initials = "";
        var userRGB  = viewerUtil.getPastelColor( props.seedNumber );

        if ( props.primaryString ) {
          initials = props.primaryString
                       .split(" ")
                       .map( function( word ) { return word[0]; } );
        } else {
          initials = props.fallbackString;
        }

        this.setState({
            userColor : "rgb(" + userRGB.join(",") + ")"
          , initials  : ( initials[0] + ( initials.length > 1 ? initials[ initials.length - 1 ] : "" ) ).toUpperCase()
        });
      }
    }

  , render: function() {
      if ( this.props.iconImage ) {
        // TODO: BASE64 encoded user images from middleware
        return (
          <div className = "user-icon"
               style     = { { height : this.props.size ? this.props.size : null
                             , width  : this.props.size ? this.props.size : null } }>
            <img className="user-icon-image" src={ "data:image/jpg;base64," + this.props.iconImage } />
          </div>
        );
      } else {
        return (
          <div className = "user-icon"
               style     = { { background : this.state.userColor ? this.state.userColor : null
                             , height     : this.props.size ? this.props.size : null
                             , width      : this.props.size ? this.props.size : null } }>
            <span className = "user-initials"
                  style     = { { fontSize   : this.props.fontSize ? this.props.fontSize + "em" : null } } >
              { this.state.initials }
            </span>
          </div>
        );
      }
    }

});
