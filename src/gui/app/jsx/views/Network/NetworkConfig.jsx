// Network Configuration Overview
// ==============================

"use strict";

var componentLongName = "NetworkConfig"

import React from "react";
import TWBS from "react-bootstrap"
import _ from "lodash";

import NetworkConfigMiddleware from "../../middleware/NetworkConfigMiddleware";
import NetworkConfigStore from "../../stores/NetworkConfigStore";

import Icon from "../../components/Icon";

const NetworkConfig = React.createClass({

  getInitialState: function () {
    return this.getNetworkConfigFromStore();
  }

  , componentDidMount: function () {
    NetworkConfigStore.addChangeListener( this.handleConfigChange );
    NetworkConfigMiddleware.requestNetworkConfig();
    NetworkConfigMiddleware.subscribe( componentLongName );
  }

  , componentWillUnmount: function () {
    NetworkConfigStore.removeChangeListener( this.handleConfigChange );
    NetworkConfigMiddleware.unsubscribe( componentLongName );
  }

  , getNetworkConfigFromStore: function () {
    return { networkConfig: NetworkConfigStore.getNetworkConfig() };
  }

  , handleConfigChange: function () {
    this.setState( this.getNetworkConfigFromStore() );
  }

  , render: function () {
    let dhcpGatewayIcon = "";
    let dhcpDNSIcon = "";
    let gatewayIPv4 = "";
    let gatewayIPv6 = "";

    if ( !_.isEmpty( this.state.networkConfig ) ) {
      dhcpGatewayIcon = this.state.networkConfig.dhcp["assign_gateway"]
                      ? "check text-primary"
                      : "times text-muted";

      dhcpDNSIcon = this.state.networkConfig.dhcp["assign_dns"]
                  ? "check text-primary"
                  : "times text-muted";

      gatewayIPv4 = this.state.networkConfig.gateway.ipv4
              ? this.state.gateway.ipv4
              : "--";

      gatewayIPv6 = this.state.networkConfig.gateway.ipv6
              ? this.state.networkConfig.gateway.ipv6
              : "--";
    }

    return (
      <main>
        <div className = "network-config container-fluid">
          <TWBS.PanelGroup>
            <TWBS.Panel>
              { "DHCP" }
              <TWBS.ListGroup fill >
                <TWBS.ListGroupItem className = "network-attribute">
                  { "Assign DNS "}
                  <Icon glyph = { dhcpDNSIcon } />
                </TWBS.ListGroupItem>
                <TWBS.ListGroupItem className = "network-attribute">
                  { "Assign Gateway "}
                  <Icon glyph = { dhcpGatewayIcon } />
                </TWBS.ListGroupItem>
              </TWBS.ListGroup>
            </TWBS.Panel>
            <TWBS.Panel>
              { "Default Gateways" }
              <TWBS.ListGroup fill >
                <TWBS.ListGroupItem className = "network-attribute">
                  { "IPv4 Default Gateway: "}
                  { gatewayIPv4 }
                </TWBS.ListGroupItem>
                <TWBS.ListGroupItem className = "network-attribute">
                  { "IPv6 Default Gateway: "}
                  { gatewayIPv6 }
                </TWBS.ListGroupItem>
              </TWBS.ListGroup>
            </TWBS.Panel>
          </TWBS.PanelGroup>
        </div>
      </main> )
  }

});

export default NetworkConfig;
