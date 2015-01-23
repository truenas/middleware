/** @jsx React.DOM */

"use strict";

var React = require("react");
var TWBS  = require("react-bootstrap");

var Router = require("react-router");
var Link   = Router.Link;

var viewerUtil = require("./viewerUtil");

var DetailNavSection = React.createClass({

    propTypes: {
        entries             : React.PropTypes.array.isRequired
      , sectionName         : React.PropTypes.string.isRequired
      , searchString        : React.PropTypes.string
      , disclosureThreshold : React.PropTypes.number
    }

  , getDefaultProps: function() {
      return { disclosureThreshold: 1 };
    }

  , getInitialState: function () {
      return { disclosure: this.props.defaultDisclosureState || "open" };
    }

  , isUnderThreshold: function() {
    return this.props.entries.length <= this.props.disclosureThreshold;
  }

  , createItem: function ( rawItem, index ) {
      var searchString = this.props.searchString;
      var params = {};

      params[ this.props.itemData.param ] = rawItem[ this.props.formatData["selectionKey"] ];

      var primaryText   = rawItem[ this.props.formatData["primaryKey"] ];
      var secondaryText = rawItem[ this.props.formatData["secondaryKey"] ];

      if ( searchString.length ) {

        var markSearch = function ( searchArray ) {
          return searchArray.map( function( subString, index ) {
            if ( index === ( searchArray.length - 1 ) ) {
              return <span>{ subString }</span>;
            } else {
              return <span>{ subString }<mark>{ searchString }</mark></span>;
            }
          });
        };

        primaryText   = markSearch( primaryText.split( searchString ) );
        secondaryText = markSearch( secondaryText.split( searchString ) );
      }

      return (
        <li role      = "presentation"
            key       = { index }
            className = "disclosure-target" >
          <Link to     = { this.props.itemData.route }
                params = { params } >
            <viewerUtil.ItemIcon primaryString  = { rawItem[ this.props.formatData["secondaryKey"] ] }
                                 fallbackString = { rawItem[ this.props.formatData["primaryKey"] ] }
                                 iconImage      = { rawItem[ this.props.formatData["imageKey"] ] }
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

    propTypes: {
        Editor       : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , ItemView     : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , EditView     : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , itemData     : React.PropTypes.object.isRequired
      , filteredData : React.PropTypes.object.isRequired
      , formatData   : React.PropTypes.object.isRequired
      , displayData  : React.PropTypes.object.isRequired
      , searchString : React.PropTypes.string
    }

  // Sidebar navigation for collection

  , render: function () {
      var fd = this.props.filteredData;
      var groupedNavItems   = null;
      var remainingNavItems = null;

      if ( fd["grouped"] ) {
        groupedNavItems = fd.groups.map( function ( group, index ) {
          var disclosureState;

          if ( this.props.displayData.defaultCollapsed ) {
            disclosureState = this.props.displayData.defaultCollapsed.indexOf( group.key ) > -1 ? "closed" : "open";
          } else {
            disclosureState = "open";
          }

          if ( group.entries.length ) {
            return (
              <DetailNavSection itemData               = { this.props.itemData }
                                formatData             = { this.props.formatData }
                                searchString           = { this.props.searchString }
                                sectionName            = { group.name }
                                defaultDisclosureState = { disclosureState }
                                entries                = { group.entries }
                                activeKey              = { this.props.selectedKey } />
            );
          } else {
            return null;
          }
        }.bind(this) );
      }

      if ( fd["remaining"].entries.length ) {
        remainingNavItems = (
          <DetailNavSection itemData               = { this.props.itemData }
                            formatData             = { this.props.formatData }
                            searchString           = { this.props.searchString }
                            sectionName            = { fd["remaining"].name }
                            defaultDisclosureState = "closed"
                            entries                = { fd["remaining"].entries }
                            activeKey              = { this.props.selectedKey } />
        );
      }

      return (
        <div className = "viewer-detail">
          <div className = "viewer-detail-nav well">
            { groupedNavItems }
            { remainingNavItems }
          </div>

          <this.props.Editor inputData  = { this.props.inputData }
                             itemData   = { this.props.itemData }
                             formatData = { this.props.formatData }
                             ItemView   = { this.props.ItemView }
                             EditView   = { this.props.EditView } />
        </div>
      );
    }

});

module.exports = DetailViewer;
