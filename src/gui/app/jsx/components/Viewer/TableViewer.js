/** @jsx React.DOM */

"use strict";

var React = require("react");
var _     = require("lodash");
var TWBS  = require("react-bootstrap");

// var Editor = require("./Editor");

// Table Viewer
var TableViewer = React.createClass({
  render: function() {
    var createHeader = function( rawItem ) {
      return(
        <th key={ rawItem.id } >
          { this.props.formatData.dataKeys[rawItem]["name"] }
        </th>
      );
    }.bind(this);

    var createRows = function( rawItem ) {
      var createCell = function( cellKey ) {
        var innerContent;
        if ( typeof rawItem[cellKey] === "boolean" ) {
          innerContent = ( rawItem ? "Yes" : "No" );
        } else if ( rawItem[cellKey].length === 0 ) {
          innerContent = <span className="text-muted">{"--"}</span>;
        } else {
          innerContent = rawItem[cellKey];
        }
        return ( <td>{ innerContent }</td> );
      }.bind( this );

      return(
        <tr key={ rawItem.id } >
          { this.props.tableCols.map( createCell ) }
        </tr>
      );
    }.bind(this);

    return(
      <TWBS.Table striped bordered condensed hover responsive>
        <thead>
          <tr>
            { this.props.tableCols.map( createHeader ) }
          </tr>
        </thead>
        <tbody>
          { this.props.inputData.map( createRows ) }
        </tbody>
      </TWBS.Table>
    );
  }
});

module.exports = TableViewer;