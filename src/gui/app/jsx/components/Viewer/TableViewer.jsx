"use strict";

var React = require("react");
var _     = require("lodash");
var TWBS  = require("react-bootstrap");

var Router     = require("react-router");
var Link       = Router.Link;
var Navigation = Router.Navigation;

var viewerUtil = require("./viewerUtil");

// Table Viewer
var TableViewer = React.createClass({

    mixins: [Navigation]

  , propTypes: {
        viewData     : React.PropTypes.object.isRequired
      , inputData    : React.PropTypes.array.isRequired
      , Editor       : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , ItemView     : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , EditView     : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , searchString : React.PropTypes.string
      , filteredData : React.PropTypes.object.isRequired
      , tableCols    : React.PropTypes.array.isRequired
    }

  , getInitialState: function() {
      return {
          tableColWidths : this.getInitialColWidths( this.props.tableCols )
        , tableColOrder  : this.props.tableCols
        , sortTableBy    : null
        , sortOrder      : "none"
      };
    }

  , componentDidMount: function() {
      this.setState({ tableColWidths: this.getUpdatedColWidths( this.state.tableColOrder ) });
    }

  , handleClickOut: function( event, componentID ) {
      if ( event.dispatchMarker === componentID ) {
        this.goBack();
      }
    }

  , handleRowClick: function( selectionKey, event, componentID ) {
      var params = {};

      params[ this.props.viewData.routing["param"] ] = selectionKey;

      this.transitionTo( this.props.viewData.routing["route"], params );
    }

  , changeSortState: function( key, event ) {
      var nextSortTableBy = key;
      var nextSortOrder;

      // When the next key matches the current selection, change the sort order
      if ( this.state.sortTableBy === key ) {
        switch ( this.state.sortOrder ) {
          case "none":
            nextSortOrder = "descending";
            break;

          case "descending":
            nextSortOrder = "ascending";
            break;

          // If the user has clicked three times on the same header, clear the
          // sort and "reset" the view
          case "ascending":
            nextSortTableBy = null;
            nextSortOrder   = "none";
            break;
        }
      } else {
        nextSortOrder = "descending";
      }

      this.setState({
          sortTableBy : nextSortTableBy
        , sortOrder   : nextSortOrder
      });

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
      var thIsActive  = ( this.state.sortTableBy === key );
      var targetEntry = _.where( this.props.viewData.format["dataKeys"], { "key" : key })[0];
      return(
        <th className     = "fixed-table-header-th"
            ref           = { "COL_" + key }
            style         = {{ width: this.state.tableColWidths[ key ] }}
            key           = { index } >
          <span className="th-spacing">
            { targetEntry["name"] }
          </span>
          <div className = { "th-content sortable-table-th" + ( thIsActive ? " " + this.state.sortOrder : "" ) }
               onClick   = { this.changeSortState.bind( null, key ) } >
            { targetEntry["name"] }
          </div>
        </th>
      );
    }

  , createRows: function( item, index ) {
      return(
        <tr key={ index } onClick= { this.handleRowClick.bind( null, item[ this.props.viewData.format["selectionKey"] ] ) }>
          { this.props.tableCols.map( function( key, index ) {
              return ( <td key={ index }>{ viewerUtil.identifyAndWrite( item[ key ] ) }</td> );
            })
          }
        </tr>
      );
    }

  , render: function() {

    var tableData     = null;
    var editorContent = null;

    if ( this.props.Editor() !== null ) {
      editorContent = (
        <div className = "overlay-light editor-edit-overlay"
             onClick   = { this.handleClickOut } >
          <this.props.Editor viewData  = { this.props.viewData }
                             inputData = { this.props.inputData }
                             activeKey = { this.props.selectedKey }
                             ItemView  = { this.props.ItemView }
                             EditView  = { this.props.EditView } />
        </div>
      );
    }

    if ( this.state.sortTableBy ) {
      tableData = _.sortBy( this.props.filteredData["rawList"], this.state.sortTableBy );

      if ( this.state.sortOrder === "ascending" ) {
        tableData = tableData.reverse();
      }

    } else {
      tableData = this.props.filteredData["rawList"];
    }

    return(
      <div className = "viewer-table fixed-table-container">
        { editorContent }
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
              { tableData.map( this.createRows ) }
            </tbody>

          </TWBS.Table>
        </div>
      </div>
    );
  }

});

module.exports = TableViewer;
