// Network Configuration Overview
// ==============================

"use strict";

var componentLongName = "NetworkOverview";

import React from "react";
import TWBS from "react-bootstrap"
import _ from "lodash";

import Router from "react-router";
const Link = Router.Link;

import NM from "../../middleware/NetworkConfigMiddleware";
import NS from "../../stores/NetworkConfigStore";

import IM from "../../middleware/InterfacesMiddleware";
import IS from "../../stores/InterfacesStore";

import SM from "../../middleware/SystemMiddleware";
import SS from "../../stores/SystemStore";

import Icon from "../../components/Icon";

var InterfaceNode = React.createClass({
  /**
   * Map an array of aliases into an array of ListGroupItems representing all
   * aliases of 'family' (i.e. INET, INET6).
   * @param  {Object} interfaceData
   * @param  {String} family
   * @return {Array}
   */
  createAliasDisplayList: function ( interfaceData, family ) {
      // Only do anything if there are any aliases.
      if ( _.isEmpty( interfaceData.status ) ) {
        return [];
      }

      var aliasDisplayItems = [];
      _.each( interfaceData.status.aliases , function ( alias ) {
        if ( family === alias.family ) {
          aliasDisplayItems.push( this.createAliasDisplayItem( alias ) );
        }
      }, this );
      return aliasDisplayItems;
    }

  /**
   * Create the individual item for createAliasDisplayList.
   * @param  {Object} alias
   * @return {TWBS.ListGroupItem}
   */
  , createAliasDisplayItem: function ( alias ) {
      return (
        <TWBS.ListGroupItem className = "alias-display-item">
          <span className = "alias-item-ip">
            <strong>{ alias.address }</strong>
          </span>
          <span className = "alias-item-netmask">
            <em>{ "/" + alias.netmask + " (" + alias.broadcast + ")" }</em>
          </span>
        </TWBS.ListGroupItem>
      );
    }

  , render: function () {
      var ipv4Aliases = this.createAliasDisplayList( this.props.interfaceData
                                                    , "INET" );
      var ipv6Aliases = this.createAliasDisplayList( this.props.interfaceData
                                                    , "INET6" );

      var ipv4Section = "";
      if ( ipv4Aliases.length ) {
        ipv4Section =
          <div className="interface-address">
            <strong>IPv4:</strong>
            <TWBS.ListGroup fill>
              { ipv4Aliases }
            </TWBS.ListGroup>
          </div>;
      }

      var ipv6Section = "";
      if ( ipv6Aliases.length ) {
        ipv6Section =
          <div className="interface-address">
            <strong>IPv6:</strong>
            <TWBS.ListGroup fill>
              { ipv6Aliases }
            </TWBS.ListGroup>
          </div>;
      }

      return (
        <div className="pull-left interface-node">
          <div className="interface-header text-center">
            <Icon glyph={ this.props.interfaceData.dhcp
                      ? "check text-primary" : "times text-muted" } />
            { this.props.interfaceData.name }
            <span className="interface-type">
              { this.props.interfaceData.type }
            </span>
          </div>
          { ipv4Section }
          { ipv6Section }
          <div className="interface-address">
            <strong>MAC:</strong>
            { this.props.interfaceData.status["link-address"] }
          </div>
          <div className="text-right">
            <Link
              to="interfaces-editor"
              params={{ interfaceName: this.props.interfaceData.name }}>
              <Icon glyph='eye' />
            </Link>
          </div>
        </div>
      );
    }
});

const NetworkOverview = React.createClass({

  getInitialState: function () {
    return _.assign( this.getNetworkConfigFromStore()
                    , this.getSystemGeneralConfigFromStore()
                    , this.getInterfaceListFromStore() );
  }

  , componentDidMount: function () {
    NS.addChangeListener( this.onNetworkConfigChange );
    NM.requestNetworkConfig();

    IS.addChangeListener( this.onInterfaceListChange );
    IM.requestInterfacesList();

    SS.addChangeListener( this.onSystemGeneralConfigChange );
    SM.requestSystemGeneralConfig();
  }

  , componentWillUnmount: function () {
    NS.removeChangeListener( this.onNetworkConfigChange );

    IS.removeChangeListener( this.onInterfaceListChange );

    SS.removeChangeListener( this.onSystemGeneralConfigChange );
  }

  /**
   * Retrieve the network config values.
   * @return {Object}
   */
  , getNetworkConfigFromStore: function () {
    // Default network config values.
    var defaultNetworkConfig = {
      dhcp: {
        assign_gateway: false
        , assign_dns: false
      }
      , http_proxy: null
      , autoconfigure: false
      , dns: {
        search: []
        , servers: []
      }
      , gateway: {
        ipv4: ""
        , ipv6: ""
      }
    };

    var networkConfig = _.defaults( NS.getNetworkConfig()
                                  , defaultNetworkConfig );

    return {
      networkConfig : networkConfig
    };
  }

  /**
   * Retrieve the system general config values.
   * @return {Object}
   */
  , getSystemGeneralConfigFromStore: function () {
    // Default system general config values.
    var defaultSystemGenernalConfig = {
      timezone: ""
      , hostname: ""
      , language: ""
      , console_keymap: ""
    };

    var systemGeneralConfig = _.defaults( SS.getSystemGeneralConfig()
                                  , defaultSystemGenernalConfig );

    return {
      systemGeneralConfig : systemGeneralConfig
    };
  }

  /**
   * Retrive the list of interfaces.
   * @return {Object}
   */
  , getInterfaceListFromStore: function () {
    return {
      interfacesList : IS.getAllInterfaces()
    };
  }

  /**
   * The change event listener for network config values.
   */
  , onNetworkConfigChange: function () {
    this.setState( this.getNetworkConfigFromStore() );
  }

  /**
   * The change event listener for system general config values.
   */
  , onSystemGeneralConfigChange: function () {
    this.setState( this.getSystemGeneralConfigFromStore() );
  }

  /**
   * The change event listener for interface list
   */
  , onInterfaceListChange: function () {
    this.setState( this.getInterfaceListFromStore() );
  }

  /**
   * Handle updates on the UI inputs.
   * @param  {String} key The key of the field updated.
   * @param  {Object} evt
   */
  , handleChange: function ( key, evt ) {
    switch ( key ) {
      case "hostname":
        var systemGeneralConfig = this.state.systemGeneralConfig;
        systemGeneralConfig.hostname = evt.target.value;
        this.setState({
          systemGeneralConfig: systemGeneralConfig
        });
        break;

      case "ipv4":
        var networkConfig = this.state.networkConfig;
        networkConfig.gateway.ipv4 = evt.target.value;
        this.setState({
          networkConfig: networkConfig
        });
        break;

      case "ipv6":
        var networkConfig = this.state.networkConfig;
        networkConfig.gateway.ipv6 = evt.target.value;
        this.setState({
          networkConfig: networkConfig
        });
        break;
    }
  }

  /**
   * Save the changes on the General section.
   */
  , saveGeneralConfig: function () {
    NM.updateNetworkConfig( this.state.networkConfig );
    SM.updateSystemGeneralConfig( this.state.systemGeneralConfig );
  }

  , render: function () {
    var interfaceNodes = _.map(
      this.state.interfacesList
      , function ( _interface ) {
          return (
            <InterfaceNode interfaceData={_interface} />
          );
        }
      );

    return (
      <main>
        <div className="network-overview container-fluid">
          <div className="section">
            <div className="section-header">
              <div className="header-text">
                <Icon glyph="chevron-down" />
                General
              </div>
              <div className="header-buttons">
                <TWBS.Button
                  onClick   = { this.saveGeneralConfig }
                  bsStyle   = "primary">
                  Save
                </TWBS.Button>
              </div>
            </div>
            <div className="section-body">
              <div className="row">
                <div className="col-sm-6">
                  <div className="form-group">
                    <label className="col-xs-3">Hostname</label>
                    <div className="col-xs-9">
                      <TWBS.Input
                        type        = "text"
                        value       = {this.state.systemGeneralConfig.hostname}
                        onChange    =
                          {this.handleChange.bind( this, "hostname" )}
                        placeholder = "Hostname" />
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="col-xs-3">IPv4 Default Gateway</label>
                    <div className="col-xs-9">
                      <TWBS.Input
                        type        = "text"
                        value       = {this.state.networkConfig.gateway.ipv4}
                        onChange    =
                          {this.handleChange.bind( this, "ipv4" )}
                        placeholder = "IPv4 Default Gateway" />
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="col-xs-3">IPv6 Default Gateway</label>
                    <div className="col-xs-9">
                      <TWBS.Input
                        type        = "text"
                        value       = {this.state.networkConfig.gateway.ipv6}
                        onChange    =
                          {this.handleChange.bind( this, "ipv6" )}
                        placeholder = "IPv6 Default Gateway" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <TWBS.Panel header='Interfaces'>
            <div className="interface-node-container clearfix">
              {interfaceNodes}
            </div>
          </TWBS.Panel>
        </div>
      </main>
    );
  }

});

export default NetworkOverview;
