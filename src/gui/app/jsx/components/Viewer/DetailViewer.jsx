

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import { Link, RouteHandler } from "react-router";

import viewerCommon from "../mixins/viewerCommon";
import viewerUtil from "./viewerUtil";

import ToggleSwitch from "../common/ToggleSwitch";


var DetailNavSection = React.createClass({

    contextTypes: {
      router: React.PropTypes.func
    }

  , propTypes: {
        viewData            : React.PropTypes.object.isRequired
      , selectedItem        : React.PropTypes.oneOfType([
                                    React.PropTypes.number
                                  , React.PropTypes.string
                                ])
      , searchString        : React.PropTypes.string
      , activeKey           : React.PropTypes.string
      , sectionName         : React.PropTypes.string.isRequired
      , initialDisclosure   : React.PropTypes.string
      , disclosureThreshold : React.PropTypes.number
      , entries             : React.PropTypes.array.isRequired
    }

  , getDefaultProps: function () {
      return { disclosureThreshold: 1 };
    }

  , getInitialState: function () {
      return { disclosure: this.props.initialDisclosure || "open" };
    }

  , isUnderThreshold: function () {
      return this.props.entries.length <= this.props.disclosureThreshold;
    }

  , createItem: function ( rawItem, index ) {
      var searchString   = this.props.searchString;
      var selectionValue = rawItem[ this.props.viewData.format["selectionKey"] ];
      var params = {};

      params[ this.props.viewData.routing["param"] ] = selectionValue;

      // FIXME: quick added || "" to the end of these so some searches wont bomb out when a key is null
      var primaryText   = rawItem[ this.props.viewData.format["primaryKey"] ] || "";
      var secondaryText = rawItem[ this.props.viewData.format["secondaryKey"] ] || "";

      if ( searchString.length ) {
        primaryText   = viewerUtil.markSearch( primaryText, searchString );
        secondaryText = viewerUtil.markSearch( secondaryText, searchString );
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
        <li role      = "presentation"
            key       = { index }
            className = "disclosure-target" >
          <Link to      = { this.props.viewData.routing.route }
                params  = { params }
                onClick = { this.props.handleItemSelect.bind( null, selectionValue ) } >
            <viewerUtil.ItemIcon primaryString  = { rawItem[ this.props.viewData.format["secondaryKey"] ] }
                                 fallbackString = { rawItem[ this.props.viewData.format["primaryKey"] ] }
                                 iconImage      = { rawItem[ this.props.viewData.format["imageKey"] ] }
                                 fontIcon       = { rawItem[ this.props.viewData.format["fontIconKey"] ] }
                                 seedNumber     = { rawItem[ this.props.viewData.format["uniqueKey"] ] }
                                 fontSize       = { 1 } />
            <div className="viewer-detail-nav-item-text">
              <strong className="primary-text">{ primaryText }</strong>
              <small className="secondary-text">{ secondaryText }</small>
            </div>
            { ts }
          </Link>
        </li>
      );
    }

  , toggleDisclosure: function () {
      var nextDisclosureState;

      if ( this.state.disclosure === "open" ) {
        nextDisclosureState = "closed";
      } else {
        nextDisclosureState = "open";
      }

      this.setState({ disclosure: nextDisclosureState });
    }

  , render: function () {
      return (
        <TWBS.Nav bsStyle   = "pills"
                  stacked
                  className = { "disclosure-" + ( this.isUnderThreshold() ? "default" : this.state.disclosure ) }
                  activeKey = { this.props.selectedKey } >
          <h5 className = "viewer-detail-nav-group disclosure-toggle"
              onClick   = { this.toggleDisclosure }>
            { this.props.sectionName }
          </h5>
          { this.props.entries.map( this.createItem ) }
        </TWBS.Nav>
      );
    }

});

// Detail Viewer
var DetailViewer = React.createClass({

    mixins: [ viewerCommon ]

  , contextTypes: {
      router: React.PropTypes.func
    }

  , propTypes: {
        viewData         : React.PropTypes.object.isRequired
      , handleItemSelect : React.PropTypes.func.isRequired
      , selectedItem     : React.PropTypes.oneOfType([ React.PropTypes.number, React.PropTypes.string ])
      , searchString     : React.PropTypes.string
      , filteredData     : React.PropTypes.object.isRequired
    }

  , componentDidMount: function () {
      // TODO: This will be an array once we implement multi-select
      var params = {};
      if ( _.isNumber( this.props.selectedItem ) || _.isString( this.props.selectedItem ) ) {
        params[ this.props.viewData.routing["param"] ] = this.props.selectedItem;
        this.context.router.replaceWith( this.props.viewData.routing.route, params );
      }
    }

  , createAddEntityButton: function () {
      var addEntityButton;

      if ( this.props.viewData.addEntity && this.props.viewData.routing.addentity ) {
        addEntityButton = (
          <Link to        = { this.props.viewData.routing.addentity }
                className = "viewer-detail-add-entity">
            <TWBS.Button bsStyle   = "default"
                         className = "viewer-detail-add-entity">
              { this.props.viewData.addEntity }
            </TWBS.Button>
          </Link>
        );

      return (addEntityButton);
      }
    }

  // Sidebar navigation for collection

  , render: function () {
      var fd = this.props.filteredData;
      var groupedNavItems   = null;
      var remainingNavItems = null;
      var editorContent     = null;

      if ( fd["grouped"] ) {
        groupedNavItems = fd.groups.map( function ( group, index ) {
          var disclosureState;

          if ( this.props.viewData.display.defaultCollapsed ) {
            disclosureState = this.props.viewData.display.defaultCollapsed.indexOf( group.key ) > -1 ? "closed" : "open";
          } else {
            disclosureState = "open";
          }

          if ( group.entries.length ) {
            return (
              <DetailNavSection
                key               = { index }
                viewData          = { this.props.viewData }
                handleItemSelect  = { this.props.handleItemSelect }
                searchString      = { this.props.searchString }
                sectionName       = { group.name }
                initialDisclosure = { disclosureState }
                entries           = { group.entries } />
            );
          } else {
            return null;
          }
        }.bind(this) );
      }

      if ( fd["remaining"].entries.length ) {
        remainingNavItems = (
          <DetailNavSection
            viewData          = { this.props.viewData }
            handleItemSelect  = { this.props.handleItemSelect }
            searchString      = { this.props.searchString }
            sectionName       = { fd["remaining"].name }
            initialDisclosure = "closed"
            entries           = { fd["remaining"].entries } />
        );
      }

      if ( this.addingEntity() ) {
        editorContent = (
          <RouteHandler
            viewData  = { this.props.viewData } />
        );
      } else if ( this.dynamicPathIsActive() ) {
        editorContent = (
          <RouteHandler
            viewData  = { this.props.viewData }
            inputData = { this.props.inputData } />
        );
      } else {
        editorContent = (
          <div className="viewer-item-info">
            <h3 className="viewer-item-no-selection">{"No active selection"}</h3>
          </div>
        );
      }

      return (
        <div className = "viewer-detail">
          <div className = "viewer-detail-sidebar">
            { this.createAddEntityButton() }
            <div className = "viewer-detail-nav well">
              { groupedNavItems }
              { remainingNavItems }
            </div>
          </div>
          { editorContent }
        </div>
      );
    }

});

module.exports = DetailViewer;
