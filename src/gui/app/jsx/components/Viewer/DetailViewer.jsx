

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import { Link, RouteHandler } from "react-router";

import viewerMode from "../mixins/viewerMode";
import viewerCommon from "../mixins/viewerCommon";
import viewerUtil from "./viewerUtil";

import ToggleSwitch from "../common/ToggleSwitch";


const DetailNavSection = React.createClass(

  { contextTypes: { router: React.PropTypes.func }

  , propTypes:
      { selectedItem: React.PropTypes.oneOfType(
                        [ React.PropTypes.number
                        , React.PropTypes.string
                        ]
                      )
      , activeKey           : React.PropTypes.string
      , disclosureThreshold : React.PropTypes.number
      , entries             : React.PropTypes.array.isRequired
      , initialDisclosure   : React.PropTypes.string.isRequired
      , searchString        : React.PropTypes.string.isRequired
      , sectionName         : React.PropTypes.string.isRequired

      , keyUnique           : React.PropTypes.string.isRequired
      , keyPrimary          : React.PropTypes.string.isRequired
      , keySecondary        : React.PropTypes.string.isRequired

      , routeName           : React.PropTypes.string.isRequired
      , routeParam          : React.PropTypes.string.isRequired
      }

  , getDefaultProps: function () {
      return { disclosureThreshold: 1 };
    }

  , getInitialState: function () {
      return { disclosure: this.props.initialDisclosure };
    }

  , isUnderThreshold: function () {
      return this.props.entries.length <= this.props.disclosureThreshold;
    }

  , createItem: function ( rawItem, index ) {
      const searchString   = this.props.searchString;
      const selectionValue = rawItem[ this.props.keyUnique ];
      var params = {};
      params[ this.props.routeParam ] = selectionValue;

      var primaryText   = rawItem[ this.props.keyPrimary ];
      var secondaryText = rawItem[ this.props.keySecondary ];

      if ( searchString.length ) {
        primaryText   = viewerUtil.markSearch( primaryText, searchString );
        secondaryText = viewerUtil.markSearch( secondaryText, searchString );
      }

      return (
        <li
          role      = "presentation"
          key       = { index }
          className = "disclosure-target"
        >
          <Link
            to      = { this.props.routeName }
            params  = { params }
            onClick = { this.props.handleItemSelect
                                  .bind( null, selectionValue )
                      }
          >
            <viewerUtil.ItemIcon
              primaryString  = { rawItem[ this.props.keySecondary ] }
              fallbackString = { rawItem[ this.props.keyPrimary ] }
              seedNumber     = { String( rawItem[ this.props.keyPrimary ] )
                               + String( rawItem[ this.props.keySecondary ] )
                               }
              fontSize       = { 1 } />
            <div className="viewer-detail-nav-item-text">
              <strong className="primary-text">{ primaryText }</strong>
              <small className="secondary-text">{ secondaryText }</small>
            </div>
          </Link>
        </li>
      );
    }

  , toggleDisclosure: function () {
      this.setState(
        { disclosure: this.state.disclosure === "open"
                    ? "closed"
                    : "open"
        }
      );
    }

  , render: function () {
      return (
        <TWBS.Nav
          stacked
          bsStyle   = "pills"
          className = { "disclosure-" + this.isUnderThreshold()
                                      ? "default"
                                      : this.state.disclosure
                      }
          activeKey = { this.props.selectedKey }
        >
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
const DetailViewer = React.createClass(

  { mixins: [ viewerMode, viewerCommon ]

  , propTypes:
    { collapsedInitial: React.PropTypes.instanceOf( Set ).isRequired
    }

  , componentDidMount: function () {
      // TODO: This will be an array once we implement multi-select
      if ( this.props.selectedItem ) {
        let params = {};
        params[ this.props.routeParam ] = this.props.selectedItem;
        this.context.router.replaceWith( this.props.routeName, params );
      }
    }

  , createAddEntityButton: function () {
      let addEntityButton = null;

      if ( this.props.textNewItem && this.props.routeAdd ) {
        addEntityButton = (
          <Link to        = { this.props.routeAdd }
                className = "viewer-detail-add-entity">
            <TWBS.Button bsStyle   = "default"
                         className = "viewer-detail-add-entity">
              { this.props.textNewItem }
            </TWBS.Button>
          </Link>
        );

      }

      return addEntityButton;
    }

  // Sidebar navigation for collection

  , render: function () {
      const FILTERED_DATA = this.props.filteredData;
      var groupedNavItems   = null;
      var remainingNavItems = null;
      var editorContent     = null;

      if ( FILTERED_DATA["grouped"] ) {
        groupedNavItems = FILTERED_DATA.groups.map( function ( group, index ) {
          let disclosureState;

          if ( this.props.collapsedInitial.size > 0 ) {
            disclosureState = this.props.collapsedInitial.has( group.key )
                            ? "closed"
                            : "open";
          } else {
            disclosureState = "open";
          }

          if ( group.entries.length ) {
            return (
              <DetailNavSection { ...this.getRequiredProps() }
                handleItemSelect  = { this.props.handleItemSelect }
                key               = { index }
                initialDisclosure = { disclosureState }
                sectionName       = { group.name }
                entries           = { group.entries } />
            );
          } else {
            return null;
          }
        }.bind( this ) );
      }

      if ( FILTERED_DATA["remaining"].entries.length ) {
        remainingNavItems = (
          <DetailNavSection { ...this.getRequiredProps() }
            handleItemSelect  = { this.props.handleItemSelect }
            initialDisclosure = "closed"
            sectionName       = { FILTERED_DATA["remaining"].name }
            entries           = { FILTERED_DATA["remaining"].entries } />
        );
      }

      if ( this.addingEntity() ) {
        editorContent = (
          <RouteHandler { ...this.props }/>
        );
      } else if ( this.dynamicPathIsActive() ) {
        editorContent = (
          <RouteHandler { ...this.getRequiredProps() }
            inputData = { this.props.inputData }
          />
        );
      } else {
        editorContent = (
          <div className="viewer-item-info">
            <h3 className="viewer-item-no-selection">
              {"No active selection"}
            </h3>
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

export default DetailViewer;
