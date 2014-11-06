/** @jsx React.DOM */

"use strict";

var React = require("react");
var _     = require("lodash");

var Editor = React.createClass({
    render: function() {
      var innerstuff = [];

      // Create line items for editor form
      var createForm = function( item ) {
        var createField = function( inputValue ) {
          switch ( typeof inputValue ){
            case "boolean":
              return ( inputValue ? "Yes" : "No" );
            default:
              return ( inputValue );
          }
        };

        innerstuff.push(
          <span>
            <dt><b>{ this.props.formatData.dataKeys[ item ]["name"] }</b></dt>
            <dd>{ createField( this.props.inputData[ item ] ) }</dd>
            <br />
          </span>
        );
      }.bind(this);

      _.chain( this.props.formatData.dataKeys)
       .keys()
       .forEach( createForm );

      return (
        <div>
          <h2>{ this.props.formatData.dataKeys[ this.props.formatData["primaryKey"] ]["name"] }</h2>
          <dl>
            { innerstuff }
          </dl>
        </div>
      );
    }
});

module.exports = Editor;