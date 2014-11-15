/** @jsx React.DOM */

"use strict";

var React = require("react");
var _     = require("lodash");
var TWBS  = require("react-bootstrap");

// Table Viewer
var TableViewer = React.createClass({
  render: function() {
    var createHeader = function( key ) {
      var targetKey = _.where( this.props.formatData.dataKeys, { "key" : key })[0];
      return(
        <th key={ key.id } >
          { targetKey["name"] }
        </th>
      );
    }.bind(this);

    var createRows = function( item ) {
      var createCell = function( cellKey ) {
        var innerContent;
        if ( typeof item[cellKey] === "boolean" ) {
          innerContent = ( item ? "Yes" : "No" );
        } else if ( item[cellKey].length === 0 ) {
          innerContent = <span className="text-muted">{"--"}</span>;
        } else {
          innerContent = item[cellKey];
        }
        return ( <td key={ cellKey.id }>{ innerContent }</td> );
      }.bind( this );

      return(
        <tr key={ item.id } >
          { this.props.tableCols.map( createCell ) }
        </tr>
      );
    }.bind(this);

    return(
      <TWBS.Table striped bordered condensed hover responsive
                  className = "viewer-table">
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