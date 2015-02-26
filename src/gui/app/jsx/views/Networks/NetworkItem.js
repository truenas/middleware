/** @jsx React.DOM */

// Networks Item Template
// ======================
// Handles viewing and and changing of network interfaces.

"use strict";

var _     = require("lodash");
var React = require("react");

var viewerUtil = require("../../components/Viewer/viewerUtil");
var editorUtil = require("../../components/Viewer/Editor/editorUtil");

var NetworksMiddleware = require("../../middleware/NetworksMiddleware");
var NetworksStore      = require("../../stores/NetworksStore");

var TWBS  = require("react-bootstrap");
var Icon   = require("../../components/Icon");

var NetworksView = React.createClass({

    propTypes: {
      item: React.PropTypes.object.isRequired
    }

  , render: function() {

      var configureButton = null;

      configureButton = (
        <TWBS.Row>
          <TWBS.Col xs={12}>
            <TWBS.Button className = "pull-right"
                         bsStyle   = "primary">{"Configure Interface"}
            </TWBS.Button>
          </TWBS.Col>
        </TWBS.Row>
      );

      return (
        <TWBS.Grid fluid>

          { configureButton }

          <TWBS.Row>
            <TWBS.Col xs={3}
                      className="text-center">
              <viewerUtil.ItemIcon fontIcon       = { this.props.item["font_icon"] }
                                   primaryString  = { this.props.item["ip"] }
                                   fallbackString = { this.props.item["name"] } />
            </TWBS.Col>
            <TWBS.Col xs={9}>
              <h3>{ this.props.item["name"] }</h3>
              <h4 className = "text-muted">{ viewerUtil.writeString( this.props.item["ip"], "\u200B" ) }</h4>
              <h4 className = "text-muted">{ viewerUtil.writeString( this.props.item["type"] ) }</h4>
              <hr />
            </TWBS.Col>
          </TWBS.Row>

          <TWBS.Row>
            <viewerUtil.DataCell title  = { this.props.item["ip_version"] + " Address" }
                                 colNum = { 2 }
                                 entry  = { this.props.item["ip"] } />
            <viewerUtil.DataCell title  = { "DHCP" }
                                 colNum = { 2 }
                                 entry  = { this.props.item["dhcp"] ? "Enabled" : "Disabled" } />
          </TWBS.Row>
          <TWBS.Row>
            <viewerUtil.DataCell title  = { "Netmask" }
                                 colNum = { 2 }
                                 entry  = {  this.props.item["netmask"] ? "/" + this.props.item["netmask"] : "N/A" } />
            <viewerUtil.DataCell title  = { "IPv6 Address" }
                                 colNum = { 2 }
                                 entry  = { "--" } />
          </TWBS.Row>
        </TWBS.Grid>
      );
    }

});

var NetworkItem = React.createClass({

    propTypes: {
        viewData : React.PropTypes.object.isRequired
      , params   : React.PropTypes.any
    }

  , getInitialState: function() {
    return {
        targetNetwork  : this.getNetworkFromStore()
      , currentMode : "view"
    };
    }

  , componentDidUpdate: function(prevProps, prevState) {
      if ( this.props.params[ this.props.viewData.routing["param"] ] !== prevProps.params[ this.props.viewData.routing["param"] ] ) {
        this.setState({
            targetNetwork  : this.getNetworkFromStore()
          , currentMode : "view"
        });
      }
    }

  , componentDidMount: function() {
      NetworksStore.addChangeListener( this.updateNetworkInState );
    }

  , componentWillUnmount: function() {
      NetworksStore.removeChangeListener( this.updateNetworkInState );
    }

  , getNetworkFromStore: function() {
      return NetworksStore.findNetworkByKeyValue( this.props.viewData.format["selectionKey"], this.props.params[ this.props.viewData.routing["param"] ] );
    }

  , updateNetworkInState: function() {
      this.setState({ targetNetwork: this.getNetworkFromStore() });
    }

  , handleViewChange: function ( nextMode, event ) {
      this.setState({ currentMode: nextMode });
    }

  , render: function() {

      var DisplayComponent = null;

        switch ( this.state.currentMode ) {
        default:
        case "view":
          DisplayComponent = NetworksView;
          break;
      }

      return (
        <div className="viewer-item-info">

        <DisplayComponent handleViewChange = { this.handleViewChange }
                          item             = { this.state.targetNetwork }
                          dataKeys         = { this.props.viewData.format["dataKeys"] } />

      </div>
      );
    }

});

module.exports = NetworkItem;
