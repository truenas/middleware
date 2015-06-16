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

var NetworkAttribute = React.createClass({
  render: function () {
    return (
      <div className="col-sm-6 row form-group">
        <label className="col-sm-4">
          {this.props.name}:
        </label>
        <div className="col-sm-8">
          {this.props.value}
        </div>
      </div>
    );
  }
});

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
    var gateway = this.state.networkConfig.gateway || {};

    var attributes =
      [ { name: 'Hostname'
        , value: 'FREENAS-MINI'
        }
      , { name: 'IPv4 Default Gateway'
        , value: gateway.ipv4 || 'Not Used'
        }
      , { name: 'Domain'
        , value: 'office.local'
        }
      , { name: 'IPv6 Default Gateway'
        , value: gateway.ipv6 || 'Not Used'
        }
      , { name: 'Interfaces'
        , value: '4'
        }
      , { name: 'Link Aggregation'
        , value: '2'
        }
      , { name: 'Static Routes'
        , value: '3'
        }
      , { name: 'VLANs'
        , value: '1'
        }
      ];

    var attributeNodes = _.map(attributes, function (attribute) {
      return (
        <NetworkAttribute name={attribute.name} value={attribute.value} />
      );
    });

    return (
      <main>
        <div className = "network-config container-fluid">
          <TWBS.Panel header='General'>
            <div className="row">
              {attributeNodes}
            </div>
          </TWBS.Panel>
        </div>
      </main>
    );
  }

});

export default NetworkConfig;
