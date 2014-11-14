/** @jsx React.DOM */

"use strict";

var React = require("react");
var _     = require("lodash");
var TWBS  = require("react-bootstrap");

var Router = require("react-router");
var Link   = Router.Link;

// Detail Viewer
var DetailViewer = React.createClass({
   propTypes: {
      defaultMode  : React.PropTypes.string
    , allowedModes : React.PropTypes.array
    , itemData     : React.PropTypes.object.isRequired
    , inputData    : React.PropTypes.array.isRequired
    , formatData   : React.PropTypes.object.isRequired
  }
  , handleChangeItem: function( key ) {
      // Pass selected key back to controller for global use
      this.props.handleItemSelect( key );
    }
  , render: function() {
    // Sidebar navigation for collection
    var createItem = function( rawItem ) {
      var params = {};
      params[ this.props.itemData.param ] = rawItem[ this.props.formatData["selectionKey"] ];
      return (
        <li role="presentation">
          <Link key             = { rawItem[ this.props.formatData["selectionKey"] ] }
                to              = { this.props.itemData.route }
                params          = { params } >
            <strong className="primary-text">{ rawItem[ this.props.formatData["primaryKey"] ] }</strong>
            <small className="secondary-text">{ rawItem[ this.props.formatData["secondaryKey"] ] }</small>
          </Link>
        </li>
      );
    }.bind(this);

    return (
      <TWBS.Grid fluid
                 className = "viewer-detail">
        <TWBS.Row>
          <TWBS.Col xs={3}>
            <TWBS.Nav bsStyle   = "pills"
                      className = "well"
                      stacked
                      activeKey = { this.props.selectedKey } >
              { this.props.inputData.map( createItem ) }
            </TWBS.Nav>
          </TWBS.Col>
          <TWBS.Col xs={9}>
            <this.props.Editor inputData  = { this.props.inputData }
                               itemData   = { this.props.itemData }
                               formatData = { this.props.formatData } />
          </TWBS.Col>
        </TWBS.Row>
      </TWBS.Grid>
    );
  }
});

module.exports = DetailViewer;