/** @jsx React.DOM */

"use strict";

var React = require("react");
var _     = require("lodash");
var TWBS  = require("react-bootstrap");

var editorUtil = require("./Editor/editorUtil");

// Table Viewer
var TableViewer = React.createClass({

    propTypes: {
        Editor       : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , ItemView     : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , filteredData : React.PropTypes.object.isRequired
      , formatData   : React.PropTypes.object.isRequired
      , inputData    : React.PropTypes.array
      , searchString : React.PropTypes.string
      , tableCols    : React.PropTypes.array.isRequired
    }

  , createHeader: function( key, index ) {
      var targetKey = _.where( this.props.formatData.dataKeys, { "key" : key })[0];
      return(
        <th key={ index } >
          { targetKey["name"] }
        </th>
      );
    }

  , createRows: function( item, index ) {
      return(
        <tr key={ index } >
          { this.props.tableCols.map( function( key, index ) {
              return ( <td key={ index }>{ editorUtil.identifyAndWrite( item[ key ] ) }</td> );
            })
          }
        </tr>
      );
    }

  , render: function() {

    return(
      <div className = "viewer-table">
        <TWBS.Table striped bordered condensed hover responsive>

          <thead>
            <tr>
              { this.props.tableCols.map( this.createHeader ) }
            </tr>
          </thead>

          <tbody>
            { this.props.filteredData["rawList"].map( this.createRows ) }
          </tbody>

        </TWBS.Table>
      </div>
    );
  }

});

module.exports = TableViewer;
