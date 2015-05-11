

"use strict";

import React from "react";
import _ from "lodash";
import TWBS from "react-bootstrap";

import { Link, RouteHandler } from "react-router";

import Icon from "../Icon";

import viewerCommon from "../mixins/viewerCommon";
import viewerUtil from "./viewerUtil";

// Table Viewer
var TableViewer = React.createClass({

    mixins: [ viewerCommon ]

  , contextTypes: {
      router: React.PropTypes.func
    }

  , propTypes: {
        viewData         : React.PropTypes.object.isRequired
      , inputData        : React.PropTypes.array.isRequired
      , handleItemSelect : React.PropTypes.func.isRequired
      , selectedItem     : React.PropTypes.oneOfType([ React.PropTypes.number, React.PropTypes.string ])
      , searchString     : React.PropTypes.string
      , filteredData     : React.PropTypes.object.isRequired
      , tableCols        : React.PropTypes.array.isRequired
    }

  , getInitialState: function () {
      return {
          tableColWidths : this.getInitialColWidths( this.props.tableCols )
        , tableColOrder  : this.props.tableCols
        , sortTableBy    : null
        , sortOrder      : "none"
      };
    }

  , componentDidMount: function () {
      this.setState({ tableColWidths: this.getUpdatedColWidths( this.state.tableColOrder ) });
      window.addEventListener( "keyup", this.handleEscClose );
    }

  , componentWillUnmount: function () {
      window.removeEventListener( "keyup", this.handleEscClose );
    }

  , handleEscClose: function( event ) {
      if ( event.which === 27 && this.dynamicPathIsActive() ) {
        event.preventDefault();
        event.stopPropagation();
        this.returnToViewerRoot();
      }
    }

  , handleClickOut: function( event, componentID ) {
      if ( event.dispatchMarker === componentID ) {
        this.returnToViewerRoot();
      }
    }

  , handleRowClick: function( params, selectionValue, event, componentID ) {
      switch ( event.type ) {
        case "click":
          this.props.handleItemSelect( selectionValue );
          break;

        case "dblclick":
          this.context.router.transitionTo( this.props.viewData.routing.route, params );
          break;
      }
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
      var selectionValue = item[ this.props.viewData.format["selectionKey"] ];
      var params         = {};

      params[ this.props.viewData.routing["param"] ] = selectionValue;

      return(
        <tr
          key           = { index }
          className     = { this.props.selectedItem === selectionValue ? "active" : "" }
          onClick       = { this.handleRowClick.bind( null, null, selectionValue ) }
          onDoubleClick = { this.handleRowClick.bind( null, params, selectionValue ) } >
          { this.props.tableCols.map( function( key, index ) {
              return ( <td key={ index }>{ viewerUtil.identifyAndWrite( item[ key ] ) }</td> );
            })
          }
        </tr>
      );
    }

  , render: function () {

    var tableData     = null;
    var editorContent = null;

    if ( this.dynamicPathIsActive() ) {
      editorContent = (
        <div className = "overlay-light editor-edit-overlay"
             onClick   = { this.handleClickOut } >
          <div className="editor-edit-wrapper">
            <span className="clearfix">
              <Icon
                glyph    = "close"
                icoClass = "editor-close"
                onClick  = { this.handleClickOut } />
            </span>
            <RouteHandler
              viewData  = { this.props.viewData }
              inputData = { this.props.inputData }
              activeKey = { this.props.selectedKey } />
          </div>
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
