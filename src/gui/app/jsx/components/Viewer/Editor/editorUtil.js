/** @jsx React.DOM */

// Editor Utilities
// ================
// A group of utility functions designed to make the creation of Editor/Viewer
// templates simpler and more straightforward.

"use strict";

// var React = require("react");
var TWBS  = require("react-bootstrap");

// var Icon  = require("../../../components/Icon");

var editorUtil = exports;

editorUtil.identifyAndCreateFormElement = function ( value, displayKeys, changeHandler ) {
  var formElement;

  switch ( displayKeys["formElement"] ) {
    case "input":
      formElement = editorUtil.createInput( value, displayKeys, changeHandler );
      break;

    case "textarea":
      formElement = editorUtil.createTextarea( value, displayKeys, changeHandler );
      break;

    case "checkbox":
      formElement = editorUtil.createCheckbox( value, displayKeys, changeHandler );
      break;

    default:
      if ( displayKeys["formElement"] ) {
        console.warn( displayKeys["formElement"] + " for value '" + value + "' is of unrecognized type" );
      } else {
        console.warn( value + " didn't have a defined formElement property" );
      }
      formElement = editorUtil.createInput( value, displayKeys, changeHandler );
      break;
  }

  return formElement;

};

editorUtil.createInput = function ( value, displayKeys, changeHandler ) {

  return(
    <TWBS.Input type        = "text"
           label            = { displayKeys["name"] }
           value            = { value }
           onChange         = { changeHandler.bind( null, displayKeys["key"] ) }
           labelClassName   = "col-xs-4"
           wrapperClassName = "col-xs-8" />
  );
};

editorUtil.createTextarea = function ( value, displayKeys, changeHandler ) {
  return(
    <TWBS.Input type        = "textarea"
           label            = { displayKeys["name"] }
           value            = { value }
           onChange         = { changeHandler.bind( null, displayKeys["key"] ) }
           labelClassName   = "col-xs-4"
           wrapperClassName = "col-xs-8" />
  );
};