// Viewer Utilities
// ================
// A group of utility functions for the Viewer and associated content.

"use strict";

import React from "react";
import TWBS from "react-bootstrap";

import Icon from "../../components/Icon";

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

viewerUtil.markSearch = function ( fullString, searchString ) {
  var i = 0;
  var splitIndex = 0;
  var searchIndex = 0;
  var splitString = [''];
  fullString = fullString.toString();
  var strLower = fullString.toLowerCase();

  while ( i < fullString.length ) {
    searchIndex = i + searchString.length;
    if ( searchIndex <= fullString.length ) {
      // if a match is found, push it onto the splitString and continue
      if ( strLower.substring(i, searchIndex) === searchString.toLowerCase() ) {
        splitString.push(fullString.substring(i, searchIndex));
        splitString.push('');
        i = searchIndex;
        splitIndex += 2;
      } else {
      // otherwise keep going we haven't found a match
        splitString[splitIndex] += fullString[i];
        i++;
      }
    } else {
      splitString[splitIndex] += fullString[i];
      i++;
    }
  }

  return splitString.map( function( subString, index ) {
    if ( subString.toLowerCase() === searchString.toLowerCase() ) {
      return <span><mark>{ subString }</mark></span>;
    } else {
      return <span>{ subString }</span>;
    }
  });
};

viewerUtil.ItemIcon = React.createClass({

    propTypes: {
        iconImage       : React.PropTypes.string
      , fontIcon        : React.PropTypes.string
      , size            : React.PropTypes.number
      , fontSize        : React.PropTypes.number
      , primaryString   : React.PropTypes.any
      , fallbackString  : React.PropTypes.any.isRequired
      , seedNumber      : React.PropTypes.number
    }

  , getDefaultProps: function () {
      return {
          size     : null
        , fontSize : null
      };
    }

  , componentWillMount: function () {
      this.setIcon( this.props );
  }

  , componentWillReceiveProps: function( nextProps ) {
      this.setIcon( this.props );
  }

  , setIcon: function( props ) {
      // If there's a profile picture already, don't bother with an icon.
      if ( !props.iconImage ) {
        // Font Icon overrides initials icon, but only needs a color.
        if ( props.fontIcon ) {
          this.setIconColor ( this.props );
        } else {
          this.setInitialsIcon( this.props );
        }
      }
    }

  , setInitialsIcon: function( props ) {
      var initials = "";

      if ( props.primaryString ) {
        initials = props.primaryString.toString()
                     .trim()
                     .split(" ")
                     .map( function( word ) { return word[0]; } );
      } else {
        initials = props.fallbackString;
      }

      this.setState({
        initials  : ( initials[0] + ( initials.length > 1 ? initials[ initials.length - 1 ] : "" ) ).toUpperCase()
      });

      this.setIconColor( this.props );
    }

  , setIconColor: function ( props ) {
      var userRGB;

      if ( typeof props.seedNumber === "number" ) {
        userRGB = viewerUtil.getPastelColor( props.seedNumber );
      } else {
        userRGB = viewerUtil.getPastelColor( props.primaryString.length + props.fallbackString.length );
      }

      this.setState({
        userColor : "rgb(" + userRGB.join(",") + ")"
      });
    }

  , render: function () {
      if ( this.props.iconImage ) {
        // TODO: BASE64 encoded user images from middleware
        return (
          <div className = "icon"
               style     = { { height : this.props.size
                             , width  : this.props.size } }>
            <img className="image-icon" src={ "data:image/jpg;base64," + this.props.iconImage } />
          </div>
        );
      } else if ( this.props.fontIcon ) {
        // Use a Font Icon, but only if there isn't a specific image specified.
        return (
          <div className = "icon"
               style     = { { background : this.state.userColor ? this.state.userColor : null
                             , height     : this.props.size
                             , width      : this.props.size } }>
            <span className = "font-icon"
                  style     = { { fontSize : this.props.fontSize + "em" } } >
              <Icon glyph     = { this.props.fontIcon } />
            </span>
          </div>
        );
      } else {
        // Using the Initials icon is a last resort.
        return (
          <div className = "icon"
               style     = { { background : this.state.userColor ? this.state.userColor : null
                             , height     : this.props.size
                             , width      : this.props.size } }>
            <span className = "initials-icon"
                  style     = { { fontSize : this.props.fontSize + "em"} } >
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
      return viewerUtil.writeString( entry );

    case "number":
      return viewerUtil.writeString( entry, "0" );

    case "boolean":
      return viewerUtil.writeBool( entry );

    default:
      return false;
  }
};

// Return a string if it's defined and non-zero length.
viewerUtil.writeString = function( entry, falseValue ) {
  if ( entry ) {
    return entry;
  } else {
    // Allow a choice of fallback string.
    return falseValue ? falseValue : "--";
  }
};

// Return a check mark if true, X mark if false.
viewerUtil.writeBool = function( entry ) {
  if ( entry ) {
    return (
      <Icon className = "text-primary"
            glyph     = "check" />
    );
  } else {
    return (
      <Icon className = "text-muted"
             glyph    = "times" />
    );
  }
};

// A simple data cell whose title is a string, and whose value is represented
// based on its type (eg. check mark for boolean). colNum is used to scale the
// output to the number of columns desired. Only 2, 3, and 4 should be used.
// On small screens, the number of columns is always 2.
viewerUtil.DataCell = React.createClass({
    propTypes: {
        title  : React.PropTypes.string.isRequired
      , colNum : React.PropTypes.number.isRequired
      , entry  : React.PropTypes.oneOfType([
            React.PropTypes.string
          , React.PropTypes.bool
          , React.PropTypes.number
        ]).isRequired
    }
  , render: function () {
      if ( typeof this.props.entry !== "undefined" ) {
        return (
          <TWBS.Col className="text-center"
                    xs={6} sm={12/this.props.colNum}>
            <h4 className="text-muted">{ this.props.title }</h4>
            <h4>{ viewerUtil.identifyAndWrite( this.props.entry ) }</h4>
          </TWBS.Col>
        );
      } else {
        return null;
      }
    }
});
