

"use strict";

import React from "react";

import { Link, RouteHandler } from "react-router";

import Icon from "../Icon";

import viewerCommon from "../mixins/viewerCommon";
import viewerUtil from "./viewerUtil";

import ToggleSwitch from "../common/ToggleSwitch";

// Icon Viewer
var IconViewer = React.createClass({

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
    }

  , componentDidMount: function () {
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

  , handleItemClick: function( params, selectionValue, event ) {
      switch ( event.type ) {
        case "click":
          this.props.handleItemSelect( selectionValue );
          break;

        case "dblclick":
          this.context.router.transitionTo( this.props.viewData.routing.route, params );
          break;
      }
    }

  , createItem: function( rawItem ) {
      var searchString   = this.props.searchString;
      var selectionValue = rawItem[ this.props.viewData.format["selectionKey"] ];
      var params = {};

      params[ this.props.viewData.routing["param"] ] = selectionValue;

      var primaryText   = rawItem[ this.props.viewData.format["primaryKey"] ];
      var secondaryText = rawItem[ this.props.viewData.format["secondaryKey"] ];

      if ( searchString.length ) {
        primaryText   = viewerUtil.markSearch( primaryText.split( searchString ), searchString );
        secondaryText = viewerUtil.markSearch( secondaryText.split( searchString ), searchString );
      }

      var ts = null;
      if ( this.props.viewData.display.showToggleSwitch )
      {
        var serviceState = (secondaryText === "running" ? true : false);
        ts = <ToggleSwitch
                toggled   = { serviceState }
                onChange  = { this.props.viewData.display.handleToggle.bind( null, rawItem ) } />;
      }

      return (
        <div
          className     = { "viewer-icon-item" + ( selectionValue === this.props.selectedItem ? " active" : "" ) }
          onClick       = { this.handleItemClick.bind( null, null, selectionValue ) }
          onDoubleClick = { this.handleItemClick.bind( null, params, selectionValue ) } >
          <viewerUtil.ItemIcon primaryString  = { rawItem[ this.props.viewData.format["secondaryKey"] ] }
                               fallbackString = { rawItem[ this.props.viewData.format["primaryKey"] ] }
                               iconImage      = { rawItem[ this.props.viewData.format["imageKey"] ] }
                               fontIcon       = { rawItem[ this.props.viewData.format["fontIconKey"] ] }
                               seedNumber     = { rawItem[ this.props.viewData.format["uniqueKey"] ] }
                               fontSize       = { 1 } />
          <div className="viewer-icon-item-text">
            <h6 className="viewer-icon-item-primary">{ primaryText }</h6>
            <small className="viewer-icon-item-secondary">{ secondaryText }</small>
            { ts }
          </div>
        </div>
      );
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
              <RouteHandler
                viewData  = { this.props.viewData }
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
        }.bind(this) );
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

module.exports = IconViewer;
