"use strict";

var React = require("react");

var Router     = require("react-router");
var Link       = Router.Link;
var Navigation = Router.Navigation;

var viewerUtil = require("./viewerUtil");

// Icon Viewer
var IconViewer = React.createClass({

    mixins: [Navigation]

  , propTypes: {
        viewData     : React.PropTypes.object.isRequired
      , inputData    : React.PropTypes.array.isRequired
      , Editor       : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , ItemView     : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , EditView     : React.PropTypes.any // FIXME: Once these are locked in, they should be the right thing
      , searchString : React.PropTypes.string
      , filteredData : React.PropTypes.object.isRequired
    }

  , handleClickOut: function( event, componentID ) {
      if ( event.dispatchMarker === componentID ) {
        this.goBack();
      }
    }

  , createItem: function( rawItem ) {
      var searchString = this.props.searchString;
      var params = {};

      params[ this.props.viewData.routing["param"] ] = rawItem[ this.props.viewData.format["selectionKey"] ];

      var primaryText   = rawItem[ this.props.viewData.format["primaryKey"] ];
      var secondaryText = rawItem[ this.props.viewData.format["secondaryKey"] ];

      if ( searchString.length ) {
        primaryText   = viewerUtil.markSearch( primaryText.split( searchString ), searchString );
        secondaryText = viewerUtil.markSearch( secondaryText.split( searchString ), searchString );
      }

      return (
        <Link to        = { this.props.viewData.routing.route }
              params    = { params }
              key       = { rawItem.id }
              className = "viewer-icon-item" >
          <viewerUtil.ItemIcon primaryString  = { rawItem[ this.props.viewData.format["secondaryKey"] ] }
                               fallbackString = { rawItem[ this.props.viewData.format["primaryKey"] ] }
                               iconImage      = { rawItem[ this.props.viewData.format["imageKey"] ] }
                               fontIcon       = { rawItem[ this.props.viewData.format["fontIconKey"] ] }
                               seedNumber     = { rawItem[ this.props.viewData.format["uniqueKey"] ] }
                               fontSize       = { 1 } />
          <div className="viewer-icon-item-text">
            <h6 className="viewer-icon-item-primary">{ primaryText }</h6>
            <small className="viewer-icon-item-secondary">{ secondaryText }</small>
          </div>
        </Link>
      );
    }

  , render: function() {
      var fd = this.props.filteredData;
      var editorContent      = null;
      var groupedIconItems   = null;
      var remainingIconItems = null;

      if ( this.props.Editor ) {
        editorContent = (
          <div className = "overlay-light editor-edit-overlay"
               onClick   = { this.handleClickOut } >
            <this.props.Editor viewData  = { this.props.viewData }
                               inputData = { this.props.inputData }
                               activeKey = { this.props.selectedKey }
                               ItemView  = { this.props.ItemView }
                               EditView  = { this.props.EditView } />
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
