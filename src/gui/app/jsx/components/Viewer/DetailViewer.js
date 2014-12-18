/** @jsx React.DOM */

"use strict";

var _     = require("lodash");
var React = require("react");
var TWBS  = require("react-bootstrap");

var Router = require("react-router");
var Link   = Router.Link;

var viewerUtil = require("./viewerUtil");

// Detail Viewer
var DetailViewer = React.createClass({

    propTypes: {
        itemData     : React.PropTypes.object.isRequired
      , filteredData : React.PropTypes.object.isRequired
      , formatData   : React.PropTypes.object.isRequired
    }

  // Sidebar navigation for collection
  , createItem: function ( rawItem, index ) {
      var params = {};
      params[ this.props.itemData.param ] = rawItem[ this.props.formatData["selectionKey"] ];
      var primaryText   = rawItem[ this.props.formatData["primaryKey"] ];
      var secondaryText = rawItem[ this.props.formatData["secondaryKey"] ];

      if ( this.props.searchString.length ) {
        var searchTemp    = this.props.searchString;
        var primaryTemp   = primaryText.split( searchTemp );
        var secondaryTemp = secondaryText.split( searchTemp );

        var markSearch = function ( searchArray ) {
          return searchArray.map( function( subString, index ) {
            if ( index === ( searchArray.length - 1 ) ) {
              return <span>{ subString }</span>;
            } else {
              return <span>{ subString }<mark>{ searchTemp }</mark></span>;
            }
          });
        };

        primaryText   = markSearch( primaryTemp );
        secondaryText = markSearch( secondaryTemp );
      }

      return (
        <li role = "presentation"
            key  = { index } >
          <Link to     = { this.props.itemData.route }
                params = { params } >
            <viewerUtil.ItemIcon primaryString  = { rawItem[ this.props.formatData["secondaryKey"] ] }
                                 fallbackString = { rawItem[ this.props.formatData["primaryKey"] ] }
                                 seedNumber     = { rawItem[ this.props.formatData["uniqueKey"] ] }
                                 fontSize       = { 1 } />
            <div className="viewer-detail-nav-item-text">
              <strong className="primary-text">{ primaryText }</strong>
              <small className="secondary-text">{ secondaryText }</small>
            </div>
          </Link>
        </li>
      );
    }

  , render: function () {

    var navItems;
    var fd = this.props.filteredData;

    if ( fd["grouped"] ) {
      navItems = fd.groups.map( function ( group ) {
        if ( group.entries.length ) {
          return (
            <TWBS.Nav bsStyle   = "pills"
                      stacked
                      activeKey = { this.props.selectedKey } >
              <h5 className="viewer-detail-nav-group">{ group.name }</h5>
              { group.entries.map( this.createItem ) }
            </TWBS.Nav>
          );
        } else {
          return null;
        }
      }.bind(this) );
    } else if ( fd["remaining"].entries.length ) {
      navItems = (
        <TWBS.Nav bsStyle   = "pills"
                  stacked
                  activeKey = { this.props.selectedKey } >
          { fd["remaining"].entries.map( this.createItem ) }
        </TWBS.Nav>
      );
    }

    return (
      <div className = "viewer-detail">
        <div className = "viewer-detail-nav well">
          { navItems }
        </div>

        <this.props.Editor inputData  = { this.props.inputData }
                           itemData   = { this.props.itemData }
                           formatData = { this.props.formatData }
                           ItemView   = { this.props.ItemView } />
      </div>
    );
  }

});

module.exports = DetailViewer;
