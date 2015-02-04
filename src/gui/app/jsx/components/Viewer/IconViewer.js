/** @jsx React.DOM */

"use strict";

var React = require("react");

var viewerUtil = require("./viewerUtil");

// Icon Viewer
var IconViewer = React.createClass({

    propTypes: {
        viewData     : React.PropTypes.object.isRequired
      , inputData    : React.PropTypes.array.isRequired
      , Editor       : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , ItemView     : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , EditView     : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , searchString : React.PropTypes.string
      , filteredData : React.PropTypes.object.isRequired
    }

  , createItem: function( rawItem ) {
      return (
        <div key       = { rawItem.id }
             className = "viewer-icon-item" >
          <viewerUtil.ItemIcon primaryString  = { rawItem[ this.props.viewData.format["secondaryKey"] ] }
                               fallbackString = { rawItem[ this.props.viewData.format["primaryKey"] ] }
                               iconImage      = { rawItem[ this.props.viewData.format["imageKey"] ] }
                               seedNumber     = { rawItem[ this.props.viewData.format["uniqueKey"] ] }
                               fontSize       = { 1 } />
          <div className="viewer-icon-item-text">
            <h6 className="viewer-icon-item-primary">{ rawItem[ this.props.viewData.format["primaryKey"] ] }</h6>
            <small className="viewer-icon-item-secondary text-muted">{ rawItem[ this.props.viewData.format["secondaryKey"] ] }</small>
          </div>
        </div>
      );
    }

  , render: function() {
      var fd = this.props.filteredData;
      var groupedIconItems   = null;
      var remainingIconItems = null;

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
          { groupedIconItems }
          { remainingIconItems }
        </div>
      );
    }
});

module.exports = IconViewer;
