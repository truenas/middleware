/** @jsx React.DOM */

// Viewer Utilities
// ================
// A group of utility functions for the Viewer and associated content.

"use strict";

var React = require("react");
var TWBS  = require("react-bootstrap");

var Icon  = require("../../components/Icon");

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

viewerUtil.markSearch = function ( searchArray, searchString ) {
  return searchArray.map( function( subString, index ) {
    if ( index === ( searchArray.length - 1 ) ) {
      return <span>{ subString }</span>;
    } else {
      return <span>{ subString }<mark>{ searchString }</mark></span>;
    }
  });
};

viewerUtil.ItemIcon = React.createClass({

    propTypes: {
        iconImage       : React.PropTypes.string
      , size            : React.PropTypes.number
      , fontSize        : React.PropTypes.number
      , primaryString   : React.PropTypes.string
      , fallbackString  : React.PropTypes.string.isRequired
      , seedNumber      : React.PropTypes.number
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
        var userRGB;

        if ( typeof props.seedNumber === "number" ) {
          userRGB = viewerUtil.getPastelColor( props.seedNumber );
        } else {
          userRGB = viewerUtil.getPastelColor( props.primaryString.length + props.fallbackString.length );
        }

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

// Lazy helper for potentially unknown types returned from middleware
viewerUtil.identifyAndWrite = function( entry ) {
  switch ( typeof entry ) {
    case "string":
    case "number":
      return viewerUtil.writeString( entry );

    case "boolean":
      return viewerUtil.writeBool( entry );

    default:
      return false;
  }
};

// Return a string if it's defined and non-zero length
viewerUtil.writeString = function( entry, falseValue ) {
  if ( entry ) {
    return entry;
  } else {
    return falseValue ? falseValue : "--";
  }
};

// Return a check mark if true
viewerUtil.writeBool = function( entry ) {
  if ( entry ) {
    return (
      <Icon className = "text-primary"
            glyph     = "check" />
    );
  } else {
    return "--";
  }
};

// A simple data cell whose title is a string, and whose value is represented
// based on its type (eg. check mark for boolean)
viewerUtil.DataCell = React.createClass({
    propTypes: {
        title: React.PropTypes.string.isRequired
      , entry: React.PropTypes.oneOfType([
            React.PropTypes.string
          , React.PropTypes.bool
          , React.PropTypes.number
        ]).isRequired
    }
  , render: function() {
      if ( typeof this.props.entry !== "undefined" ) {
        return (
          <TWBS.Col className="text-center"
                    xs={6} sm={4}>
            <h4 className="text-muted">{ this.props.title }</h4>
            <h4>{ viewerUtil.identifyAndWrite( this.props.entry ) }</h4>
          </TWBS.Col>
        );
      } else {
        return null;
      }
    }
});
