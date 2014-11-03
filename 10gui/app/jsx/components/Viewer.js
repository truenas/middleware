/** @jsx React.DOM */

"use strict";

var React = require("react");

var _ = require("lodash");

// Twitter Bootstrap React components
var TWBS = require("react-bootstrap");


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
            <this.props.editor inputData  = { _.find( this.props.inputData, getObjectByKey ) }
                               formatData = { this.props.formatData } />
          </TWBS.Col>
        </TWBS.Row>
      </TWBS.Grid>
    );
  }
});

// Icon Viewer
var IconViewer = React.createClass({
  render: function() {
    var createItem = function( rawItem ) {
      return (
        <TWBS.Col xs  = {2}
                  key = { rawItem.id } >
          <h6>{ rawItem[ this.props.formatData["primaryKey"] ] }</h6>
          <small className="text-muted">{ rawItem[ this.props.formatData["secondaryKey"] ] }</small>
        </TWBS.Col>
      );
    }.bind(this);

    return (
      <TWBS.Row>
        { this.props.inputData.map( createItem ) }
      </TWBS.Row>
    );
  }
});

// Table Viewer
var TableViewer = React.createClass({
  render: function() {
    var createHeader = function( key ) {
      return(
        <th key={ key.id } >
          { this.props.formatData.dataKeys[key]["name"] }
        </th>
      );
    }.bind(this);

    var createRows = function( rawItem ) {
      var createCell = function( cellKey ) {
        var innerContent;
        if ( typeof rawItem[cellKey] === "boolean" ) {
          innerContent = ( rawItem ? "Yes" : "No" );
        } else if ( rawItem[cellKey].length === 0 ) {
          innerContent = <span className="text-muted">{"--"}</span>;
        } else {
          innerContent = rawItem[cellKey];
        }
        return ( <td>{ innerContent }</td> );
      }.bind( this );

      return(
        <tr key={ rawItem.id } >
          { this.props.tableCols.map( createCell ) }
        </tr>
      );
    }.bind(this);

    return(
      <TWBS.Table striped bordered condensed hover responsive>
        <thead>
          <tr>
            { this.props.tableCols.map( createHeader ) }
          </tr>
        </thead>
        <tbody>
          { this.props.inputData.map( createRows ) }
        </tbody>
      </TWBS.Table>
    );
  }
});

// Main Viewer Component
var Viewer = React.createClass({
    changeViewMode: function( targetMode ) {
      var newMode;

      // See if a disallowed mode has been requested
      if ( this.props.allowedModes.indexOf( targetMode ) === -1 ) {
        console.log( "Error: Attempted to set mode " + targetMode + " in a Viewer which forbids it");
        if ( this.props.defaultMode ) {
          // Use the default mode, if provided
          console.log( "Note: Substituted provided default, " + this.props.defaultMode + " instead of " + targetMode );
          newMode = this.props.defaultMode;
        } else {
          // If no default, use the first allowed mode in the list
          newMode = this.props.allowedModes[0];
        }
      } else {
        newMode = targetMode;
      }

      return newMode;
   }
   , handleModeSelect: function( selectedKey ) {
      this.setState({
        currentMode: this.changeViewMode( this.props.allowedModes[ selectedKey ] )
      });
   }
   , handleItemSelect: function( selectedKey ) {
      this.setState({ selectedItem: selectedKey });
   }
   , propTypes: {
        defaultMode  : React.PropTypes.string
      , allowedModes : React.PropTypes.array
      , inputData    : React.PropTypes.array.isRequired
      , formatData   : React.PropTypes.object.isRequired
    }
  , getDefaultProps: function() {
      // Viewer allows all modes by default, except for heirarchical. This list
      // can be overwritten by passing allowedModes into your <Viewer />.
      // Allowed modes are:
      // "detail" : Items on left, with properties on right, cnofigurable
      // "icon"   : Items as icons, with properties as modal
      // "table"  : Items as table rows, showing more data
      // "heir"   : Heirarchical view, shows relationships between items
      return {
        allowedModes: [ "detail", "icon", "table" ]
      };
    }
  , getInitialState: function() {
      // render will always use currentMode - in an uninitialized Viewer, the
      // mode will not have been set, and should therefore come from either a
      // passed in currentMode or defaultMode, falling back to getDefaultProps
      var initialMode = ( this.props.currentMode || this.props.defaultMode || "detail" );

      // Generate an array of keys which TableViewer can use to quickly generate
      // its internal structure by looping through the returned data from the
      // middleware and creating cells. Also useful for getting human-friendly
      // names out of the translation key.
      var defaultTableCols = [];

      _.filter( this.props.formatData.dataKeys, function( item, key, collection ) {
        if ( item["defaultCol"] ) {
          defaultTableCols.push( key );
        }
      });

      return {
          currentMode  : this.changeViewMode( initialMode )
        , tableCols    : defaultTableCols
        , selectedItem : this.props.inputData[0][ this.props.formatData.selectionKey ]
      };
    }
  , render: function() {
    // Navigation
    var createModeNav = function( mode ) {
      return ( <TWBS.NavItem key = { this.props.allowedModes.indexOf( mode ) }>
                 { mode }
               </TWBS.NavItem> );
    }.bind(this);

    // Select view based on current mode
    var viewerContent = function() {
      switch ( this.state.currentMode ) {
        default:
        case "detail":
          return( <DetailViewer inputData        = { this.props.inputData }
                                formatData       = { this.props.formatData }
                                handleItemSelect = { this.handleItemSelect }
                                selectedKey      = { this.state.selectedItem }
                                editor           = { this.props.editor } /> );
        case "icon":
          return( <IconViewer inputData  = { this.props.inputData }
                              formatData = { this.props.formatData }
                              editor     = { this.props.editor } /> );
        case "table":
          return( <TableViewer inputData  = { this.props.inputData }
                               formatData = { this.props.formatData }
                               editor     = { this.props.editor }
                               tableCols  = { this.state.tableCols } /> );
        case "heir":
          // TODO: Heirarchical Viewer
          break;
      }
    }.bind(this);

    return (
      <TWBS.Panel header={ this.props.header }>
        <TWBS.Nav bsStyle="pills"
                  justified
                  onSelect  = { this.handleModeSelect }
                  activeKey = { this.props.allowedModes.indexOf( this.state.currentMode ) } >
          { this.props.allowedModes.map( createModeNav ) }
        </TWBS.Nav>
        { viewerContent() }
      </TWBS.Panel>
    );
  }
});

module.exports = Viewer;