// Interface Item
// ==============
// Handles viewing and and changing of network interfaces.

"use strict";

import React from "react";

import routerShim from "../../../components/mixins/routerShim";
import clientStatus from "../../../components/mixins/clientStatus";

import viewerUtil from "../../../components/Viewer/viewerUtil";

import InterfacesStore from "../../../stores/InterfacesStore";

import TWBS from "react-bootstrap";

var InterfacesView = React.createClass({

  propTypes: {
    item: React.PropTypes.object.isRequired
  }

  , render: function () {

    var configureButton = null;

    configureButton = (
      <TWBS.Row>
        <TWBS.Col xs={12}>
          <TWBS.Button
            className = "pull-right"
            bsStyle   = "primary">{"Configure Interface"}
          </TWBS.Button>
        </TWBS.Col>
      </TWBS.Row>
    );

    return (
      <TWBS.Grid fluid>

        { configureButton }

        <TWBS.Row>
          <TWBS.Col
            xs={3}
            className="text-center">
            <viewerUtil.ItemIcon
              fontIcon = { this.props.item["font_icon"] }
              primaryString = { this.props.item["ip"] }
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
          <viewerUtil.DataCell
            title  = { this.props.item["ip_version"] + " Address" }
            colNum = { 2 }
            entry  = { this.props.item["ip"] } />
          <viewerUtil.DataCell
            title  = { "DHCP" }
            colNum = { 2 }
            entry  = { this.props.item["dhcp"]
                       ? "Enabled"
                       : "Disabled" } />
        </TWBS.Row>
        <TWBS.Row>
          <viewerUtil.DataCell
            title  = { "Netmask" }
            colNum = { 2 }
            entry  = { this.props.item["netmask"]
                       ? "/" + this.props.item["netmask"]
                       : "N/A" } />
          <viewerUtil.DataCell
            title = { "IPv6 Address" }
            colNum = { 2 }
            entry = { "--" } />
        </TWBS.Row>
      </TWBS.Grid>
    );
  }

});

var InterfaceItem = React.createClass({

  propTypes: {
    viewData: React.PropTypes.object.isRequired
  }

  , mixins: [ routerShim, clientStatus ]

  , getInitialState: function () {
      return {
        targetInterface: this.getInterfaceFromStore()
        , currentMode: "view"
        , activeRoute: this.getDynamicRoute()
      };
    }

  , componentDidUpdate: function ( prevProps, prevState ) {
      var activeRoute = this.getDynamicRoute();

      if ( activeRoute !== prevState.activeRoute ) {
        this.setState({
          targetInterface: this.getInterfaceFromStore()
          , currentMode: "view"
          , activeRoute: activeRoute
        });
      }
    }

  , componentDidMount: function () {
      InterfacesStore.addChangeListener( this.updateInterfaceInState );
    }

  , componentWillUnmount: function () {
      InterfacesStore.removeChangeListener( this.updateInterfaceInState );
    }

  , getInterfaceFromStore: function () {
      return InterfacesStore.findInterfaceByKeyValue( this.props.viewData.format["selectionKey"]
                                                    , this.getDynamicRoute() );
    }

  , updateInterfaceInState: function () {
      this.setState({ targetInterface: this.getInterfaceFromStore() });
    }

  , handleViewChange: function ( nextMode, event ) {
      this.setState({ currentMode: nextMode });
    }

  , render: function () {

    var DisplayComponent      = null;

    if ( this.state.SESSION_AUTHENTICATED && this.state.targetInterface ) {
      var childProps = {
        handleViewChange: this.handleViewChange
        , item: this.state.targetInterface
        , dataKeys: this.props.viewData.format["dataKeys"]
      };

      switch ( this.state.currentMode ) {
        default:
        case "view":
          DisplayComponent = <InterfacesView {...childProps} />;
          break;
      }
    }

    return (
      <div className="viewer-item-info">

      { DisplayComponent }

    </div>
    );
  }

});

module.exports = InterfaceItem;
