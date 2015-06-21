

"use strict";

import React from "react";
import _ from "lodash";
import TWBS from "react-bootstrap";

import { Link, RouteHandler } from "react-router";

import Icon from "../Icon";

import viewerCommon from "../mixins/viewerCommon";
import viewerMode from "../mixins/viewerMode";
import viewerOverlay from "../mixins/viewerOverlay";
import viewerUtil from "./viewerUtil";

// Table Viewer
const TableViewer = React.createClass(

  { mixins: [ viewerOverlay, viewerMode, viewerCommon ]

  , getInitialState: function () {
      // TODO: User preferences will rescue this
      const columnArray = Array.from( this.props.columnsInitial );

      return (
        { columnWidths : this.getInitialColWidths( columnArray )
        , columnOrder  : columnArray
        , sortTableBy  : null
        , sortOrder    : "none"
        }
      );
    }

  , componentDidMount: function () {
      this.setState(
        { columnWidths: this.getUpdatedColWidths( this.state.columnOrder ) }
      );
    }

  , handleRowClick: function ( params, selectionValue, event, componentID ) {
      switch ( event.type ) {
        case "click":
          this.props.handleItemSelect( selectionValue );
          break;

        case "dblclick":
          this.context.router.transitionTo( this.props.routeName, params );
          break;
      }
    }

  , changeSortState: function ( key, event ) {
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

      this.setState(
        { sortTableBy : nextSortTableBy
        , sortOrder   : nextSortOrder
        }
      );

    }

  , getInitialColWidths: function ( columnSet ) {
      var tempWidths = {};

      columnSet.map( column => tempWidths[ column ] = "auto" );

      return tempWidths;
    }

  , getUpdatedColWidths: function ( columnSet ) {
      var tempWidths  = {};
      var viewerWidth = this.refs[ "TABLE_VIEWER" ].getDOMNode().offsetWidth;

      columnSet.map( column => {
        let colWidth = this.refs[ "COL_" + column ].getDOMNode().offsetWidth;

        tempWidths[ column ] =
          Math.round( colWidth / viewerWidth * 10000 ) / 100 + "%";
      });

      return tempWidths;
    }

  , createHeader: function ( key, index ) {
      var thIsActive  = ( this.state.sortTableBy === key );
      return (
        <th
          className = "fixed-table-header-th"
          ref       = { "COL_" + key }
          style     = {{ width: this.state.columnWidths[ key ] }}
          key       = { index }
        >
          <span className="th-spacing">
            { this.props.itemLabels[ key ] }
          </span>
          <div
            className = { "th-content sortable-table-th"
                        + ( thIsActive
                          ? " " + this.state.sortOrder
                          : ""
                          )
                        }
            onClick   = { this.changeSortState.bind( null, key ) }
          >
            { this.props.itemLabels[ key ] }
          </div>
        </th>
      );
    }

  , createRows: function ( item, index ) {
      var selectionValue = item[ this.props.keyUnique ];
      var params         = {};

      params[ this.props.routeParam ] = selectionValue;

      return (
        <tr
          key           = { index }
          className     = { this.props.selectedItem === selectionValue
                                                    ? "active"
                                                    : ""
                          }
          onClick       = { this.handleRowClick
                              .bind( null, null, selectionValue )
                          }
          onDoubleClick = { this.handleRowClick
                              .bind( null, params, selectionValue )
                          }
        >
          { this.state.columnOrder.map(
              function ( key, index ) {
                return (
                  <td key={ index }>
                    { viewerUtil.identifyAndWrite( item[ key ] ) }
                  </td>
                );
              }
            )
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
              <RouteHandler { ...this.getRequiredProps() }
                inputData = { this.props.inputData }
                activeKey = { this.props.selectedKey } />
            </div>
          </div>
        );
      }

      if ( this.state.sortTableBy ) {
        tableData = _.sortBy( this.props.filteredData["rawList"]
                            , this.state.sortTableBy );

        if ( this.state.sortOrder === "ascending" ) {
          tableData = tableData.reverse();
        }

      } else {
        tableData = this.props.filteredData["rawList"];
      }

      return (
        <div className = "viewer-table fixed-table-container">
          { editorContent }
          <div className = "fixed-table-container-inner">

            <TWBS.Table
              striped bordered condensed hover
              ref       = "TABLE_VIEWER"
              className = "fixed-table"
            >

              <thead>
                <tr>
                  { this.state.columnOrder.map( this.createHeader ) }
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
  }
);

export default TableViewer;
