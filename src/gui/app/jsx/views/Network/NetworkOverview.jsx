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
    return this.getNetworkConfigFromStore();
  }

  , componentDidMount: function () {
    NS.addChangeListener( this.handleConfigChange );
    NM.requestNetworkConfig();
    NM.subscribe( componentLongName );

    IS.addChangeListener( this.handleConfigChange );
    IM.requestInterfacesList();
    IM.subscribe( componentLongName );

    SS.addChangeListener( this.handleConfigChange );
    SM.requestSystemGeneralConfig();
  }

  , componentWillUnmount: function () {
    NS.removeChangeListener( this.handleConfigChange );
    NM.unsubscribe( componentLongName );

    IS.removeChangeListener( this.handleConfigChange );
    IM.unsubscribe( componentLongName );

    SS.removeChangeListener( this.handleConfigChange );
    SM.unsubscribe( componentLongName );
  }

  , getNetworkConfigFromStore: function () {
    return {
      networkConfig         : NS.getNetworkConfig()
      , interfacesList      : IS.getAllInterfaces()
      , systemGeneralConfig : SS.getSystemGeneralConfig()
    };
  }

  , handleConfigChange: function () {
    this.setState( this.getNetworkConfigFromStore() );
  }

  , render: function () {
    var gateway = this.state.networkConfig.gateway || {};
    var dnsServers = [];
    if ( !_.isUndefined( this.state.networkConfig.dns ) ) {
      dnsServers = this.state.networkConfig.dns.servers || [];
    }

    var dnsServersNode;
    if ( !dnsServers.length ) {
      dnsServersNode =
        <span>
          No DNS servers configured.
        </span>;
    } else {
      var items = _.map( dnsServers, function ( server ) {
        return (
          <li>{ server }</li>
        );
      });
      dnsServersNode =
        <ul className="dns-server-list">
          { items }
        </ul>;
    }

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
          <TWBS.Panel header='General'>
            <div className="form-group">
              <label className="overview-label">
                Hostname:
              </label>
              <div className="overview-value">
                { this.state.systemGeneralConfig.hostname }
              </div>
            </div>
            <div className="form-group row">
              <div className="col-sm-6">
                <label className="overview-label">
                  IPv4 Default Gateway:
                </label>
                <div className="overview-value">
                  { gateway.ipv4 || "Not Used" }
                </div>
              </div>
              <div className="col-sm-6">
                <label className="overview-label">
                  IPv6 Default Gateway:
                </label>
                <div className="overview-value">
                  { gateway.ipv6 || "Not Used" }
                </div>
              </div>
            </div>
            <div>
              <label className="overview-label">
                DNS Servers:
              </label>
              <div className="overview-value">
                { dnsServersNode }
              </div>
            </div>
          </TWBS.Panel>
          <TWBS.Panel header='Interfaces'>
            <div className="interface-node-container clearfix">
              {interfaceNodes}
              <Link to="interfaces" className="show-all">Show interfaces</Link>
            </div>
          </TWBS.Panel>
        </div>
      </main>
    );
  }

});

export default NetworkOverview;
