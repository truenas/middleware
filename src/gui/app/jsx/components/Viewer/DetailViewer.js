/** @jsx React.DOM */

"use strict";

var React = require("react");
var _     = require("lodash");
var TWBS  = require("react-bootstrap");

var Editor = require("./Editor");

// Detail Viewer
var DetailViewer = React.createClass({
    handleChangeItem: function( key ) {
      // Pass selected key back to controller for global use
      this.props.handleItemSelect( key );
    }
  , render: function() {
    // Sidebar navigation for collection
    var createItem = function( rawItem ) {
      return ( <TWBS.NavItem key={ rawItem[ this.props.formatData["selectionKey"] ] }>
                 <h4>{ rawItem[ this.props.formatData["primaryKey"] ] }</h4>
                 <small>{ rawItem[ this.props.formatData["secondaryKey"] ] }</small>
               </TWBS.NavItem> );
    }.bind(this);

    // Populate the editor pane with the object cooresponding to the current selection
    var getObjectByKey = function( item ) {
      return item[ this.props.formatData["selectionKey"] ] === this.props.selectedKey;
    }.bind(this);

    return (
      <TWBS.Grid>
        <TWBS.Row>
          <TWBS.Col xs={3}>
            <TWBS.Nav bsStyle   = "pills"
                      stacked
                      onSelect  = { this.handleChangeItem }
                      activeKey = { this.props.selectedKey } >
              { this.props.inputData.map( createItem ) }
            </TWBS.Nav>
          </TWBS.Col>
          <TWBS.Col xs={9}>
            <Editor inputData  = { _.find( this.props.inputData, getObjectByKey ) }
                    formatData = { this.props.formatData } />
          </TWBS.Col>
        </TWBS.Row>
      </TWBS.Grid>
    );
  }
});

module.exports = DetailViewer;