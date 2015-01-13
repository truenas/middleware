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

  , getInitialState: function() {
      return {
          tableColWidths : this.getInitialColWidths( this.props.tableCols )
        , tableColOrder  : this.props.tableCols
      };
    }

  , componentDidMount: function() {
      this.setState({ tableColWidths: this.getUpdatedColWidths( this.state.tableColOrder ) });
    }

  , getInitialColWidths: function( colArray ) {
      var tempWidths = {};

      colArray.map( function( targetCol, index ) {
        tempWidths[ targetCol ] = "auto";
      });

      return tempWidths;
    }

  , getUpdatedColWidths: function( colArray ) {
      var tempWidths  = {};
      var viewerRefs  = this.refs;
      var viewerWidth = this.refs[ "TABLE_VIEWER" ].getDOMNode().offsetWidth;

      colArray.map( function( targetCol, index ) {
        var colWidth = viewerRefs[ "COL_" + targetCol ].getDOMNode().offsetWidth;
        tempWidths[ targetCol ] = Math.round( colWidth / viewerWidth * 10000 ) / 100 + "%";
      });

      return tempWidths;
    }

  , createHeader: function( key, index ) {
      var targetEntry = _.where( this.props.formatData.dataKeys, { "key" : key })[0];
      return(
        <th className = "fixed-table-header-th"
            ref       = { "COL_" + key }
            style     = {{ width: this.state.tableColWidths[ key ] }}
            key       = { index } >
          <span className="th-spacing">
            { targetEntry["name"] }
          </span>
          <div className="th-content sortable-table-th">
            { targetEntry["name"] }
          </div>
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
      <div className = "viewer-table fixed-table-container">
        <div className = "fixed-table-container-inner">

          <TWBS.Table striped bordered condensed hover
                      ref       = "TABLE_VIEWER"
                      className = "fixed-table">

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
      </div>
    );
  }

});

module.exports = TableViewer;
