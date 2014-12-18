/** @jsx React.DOM */

// Editor Utilities
// ================
// A group of utility functions designed to make the creation of Editor/Viewer
// templates simpler and more straightforward.

"use strict";

var React = require("react");
var TWBS  = require("react-bootstrap");

var Icon  = require("../../../components/Icon");

var editorUtil = exports;

// Lazy helper for potentially unknown types returned from middleware
editorUtil.identifyAndWrite = function( entry ) {
  switch ( typeof entry ) {
    case "string":
    case "number":
      return editorUtil.writeString( entry );

    case "boolean":
      return editorUtil.writeBool( entry );

    default:
      return false;
  }
};

// Return a string if it's defined and non-zero length
editorUtil.writeString = function( entry, falseValue ) {
  if ( entry ) {
    return entry;
  } else {
    return falseValue ? falseValue : "--";
  }
};

// Return a check mark if true
editorUtil.writeBool = function( entry ) {
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
editorUtil.DataCell = React.createClass({
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
            <h4>{ editorUtil.identifyAndWrite( this.props.entry ) }</h4>
          </TWBS.Col>
        );
      } else {
        return null;
      }
    }
});