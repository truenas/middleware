/** @jsx React.DOM */

"use strict";

var React = require("react");
var TWBS  = require("react-bootstrap");

var Router = require("react-router");
var Link   = Router.Link;

var viewerUtil = require("./viewerUtil");

var DetailNavSection = React.createClass({

    propTypes: {
        viewData            : React.PropTypes.object.isRequired
      , searchString        : React.PropTypes.string
      , activeKey           : React.PropTypes.string
      , sectionName         : React.PropTypes.string.isRequired
      , initialDisclosure   : React.PropTypes.string
      , disclosureThreshold : React.PropTypes.number
      , entries             : React.PropTypes.array.isRequired
    }

  , getDefaultProps: function() {
      return { disclosureThreshold: 1 };
    }

  , getInitialState: function () {
      return { disclosure: this.props.initialDisclosure || "open" };
    }

  , isUnderThreshold: function() {
    return this.props.entries.length <= this.props.disclosureThreshold;
  }

  , createItem: function ( rawItem, index ) {
      var searchString = this.props.searchString;
      var params = {};

      params[ this.props.viewData.routing["param"] ] = rawItem[ this.props.viewData.format["selectionKey"] ];

      var primaryText   = rawItem[ this.props.viewData.format["primaryKey"] ];
      var secondaryText = rawItem[ this.props.viewData.format["secondaryKey"] ];

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
          <Link to     = { this.props.viewData.routing.route }
                params = { params } >
            <viewerUtil.ItemIcon primaryString  = { rawItem[ this.props.viewData.format["secondaryKey"] ] }
                                 fallbackString = { rawItem[ this.props.viewData.format["primaryKey"] ] }
                                 iconImage      = { rawItem[ this.props.viewData.format["imageKey"] ] }
                                 seedNumber     = { rawItem[ this.props.viewData.format["uniqueKey"] ] }
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
        viewData     : React.PropTypes.object.isRequired
      , Editor       : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , ItemView     : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , EditView     : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , searchString : React.PropTypes.string
      , filteredData : React.PropTypes.object.isRequired
    }

  // Sidebar navigation for collection

  , render: function () {
      var fd = this.props.filteredData;
      var groupedNavItems   = null;
      var remainingNavItems = null;

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
              <DetailNavSection viewData          = { this.props.viewData }
                                searchString      = { this.props.searchString }
                                activeKey         = { this.props.selectedKey }
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
          <DetailNavSection viewData          = { this.props.viewData }
                            searchString      = { this.props.searchString }
                            activeKey         = { this.props.selectedKey }
                            sectionName       = { fd["remaining"].name }
                            initialDisclosure = "closed"
                            entries           = { fd["remaining"].entries } />
        );
      }

      return (
        <div className = "viewer-detail">
          <div className = "viewer-detail-nav well">
            { groupedNavItems }
            { remainingNavItems }
          </div>

          <this.props.Editor viewData  = { this.props.viewData }
                             inputData = { this.props.inputData }
                             ItemView  = { this.props.ItemView }
                             EditView  = { this.props.EditView } />
        </div>
      );
    }

});

module.exports = DetailViewer;
