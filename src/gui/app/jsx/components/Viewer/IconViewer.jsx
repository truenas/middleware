

"use strict";

import React from "react";

import { Link, RouteHandler } from "react-router";

import Icon from "../Icon";

import viewerMode from "../mixins/viewerMode";
import viewerCommon from "../mixins/viewerCommon";
import viewerOverlay from "../mixins/viewerOverlay";
import viewerUtil from "./viewerUtil";

import ToggleSwitch from "../common/ToggleSwitch";

// Icon Viewer
var IconViewer = React.createClass(

  { mixins: [ viewerOverlay, viewerMode, viewerCommon ]

  , handleItemClick: function ( params, selectionValue, event ) {
      switch ( event.type ) {
        case "click":
          this.props.handleItemSelect( selectionValue );
          break;

        case "dblclick":
          this.context.router.transitionTo( this.props.routeName, params );
          break;
      }
    }

  , createItem: function ( rawItem ) {
      const search    = this.props.searchString;
      const selection = rawItem[ this.props.keyUnique ];

      let itemIcon = null;

      var params = {};

      params[ this.props.routeParam ] = selection;

      var textPrimary   = rawItem[ this.props.keyPrimary ];
      var textSecondary = rawItem[ this.props.keySecondary ];

      if ( search.length ) {
        textPrimary   = viewerUtil.markSearch(
                          textPrimary.split( search ), search
                        );
        textSecondary = viewerUtil.markSearch(
                          textSecondary.split( search ), search
                        );
      }

      if ( this.props.itemIconTemplate ) {
        itemIcon =
          <div className = { "viewer-icon-item"
                        + ( selection === this.props.selectedItem
                                        ? " active"
                                        : ""
                          )
                        }
               onClick = { this.handleItemClick.bind( null
                                                    , null
                                                    , selection ) }
               onDoubleClick = { this.handleItemClick.bind( null
                                                          , params
                                                          , selection ) } >
            <this.props.itemIconTemplate { ...rawItem } />
          </div>;
      } else {
        itemIcon =
          <div
            className = { "viewer-icon-item"
                        + ( selection === this.props.selectedItem
                                        ? " active"
                                        : ""
                          )
                        }
            onClick = { this.handleItemClick.bind( null
                                                 , null
                                                 , selection ) }
            onDoubleClick = { this.handleItemClick.bind( null
                                                       , params
                                                       , selection ) } >
              <viewerUtil.ItemIcon
                primaryString  = { rawItem[ this.props.keySecondary ] }
                fallbackString = { rawItem[ this.props.keyPrimary ] }
                seedNumber = { String( rawItem[ this.props.keyPrimary ] )
                             + String( rawItem[ this.props.keySecondary ] )
                             }
                fontSize = { 1 } />
            <div className="viewer-icon-item-text">
              <h6 className="viewer-icon-item-primary">{ textPrimary }</h6>
              <small className="viewer-icon-item-secondary">
                { textSecondary }
              </small>
            </div>
        </div>;
      }

      return itemIcon;

    }

  , render: function () {
      var fd = this.props.filteredData;
      var editorContent      = null;
      var groupedIconItems   = null;
      var remainingIconItems = null;

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

      if ( fd["grouped"] ) {
        groupedIconItems = fd.groups.map( function ( group, index ) {
          if ( group.entries.length ) {
            return (
              <div className="viewer-icon-section" key={ index }>
                <h4>{ group.name }</h4>
                <hr />
                { group.entries.map( this.createItem ) }
              </div>
            );
          } else {
            return null;
          }
        }.bind( this ) );
      }

      if ( fd["remaining"].entries.length ) {
        remainingIconItems = (
          <div className="viewer-icon-section">
            <h4>{ fd["remaining"].name }</h4>
            <hr />
            { fd["remaining"].entries.map( this.createItem ) }
          </div>
        );
      }

      return (
        <div className = "viewer-icon">
          { editorContent }
          { groupedIconItems }
          { remainingIconItems }
        </div>
      );
    }
});

export default IconViewer;
