// Network Configuration Overview
// ==============================

"use strict";

var componentLongName = "NetworkSettings";

import React from "react";
import TWBS from "react-bootstrap"
import _ from "lodash";

import NM from "../../middleware/NetworkConfigMiddleware";
import NS from "../../stores/NetworkConfigStore";

const NetworkSettings = React.createClass({

  getInitialState: function () {
    var states = this.getNetworkConfigFromStore();
    states.locallyModifiedValues = {};
    return states;
  }

  , componentDidMount: function () {
    NS.addChangeListener( this.handleConfigChange );
    NM.requestNetworkConfig();
    NM.subscribe( componentLongName );
  }

  , componentWillUnmount: function () {
    NS.removeChangeListener( this.handleConfigChange );
    NM.unsubscribe( componentLongName );
  }

  , getNetworkConfigFromStore: function () {
    var networkConfig = NS.getNetworkConfig();

    var gateway = networkConfig.gateway || {};
    var addresses = [];
    if ( !_.isUndefined( networkConfig.dns ) ) {
      addresses = networkConfig.dns.addresses || [];
    }

    var remoteState = {
      ipv4  : gateway.ipv4 || ""
      , ipv6: gateway.ipv6 || ""
      , ns1 : addresses[0] || ""
      , ns2 : addresses[1] || ""
    };

    return {
      networkConfig : networkConfig
      , remoteState : remoteState
    };
  }

  , handleConfigChange: function () {
    this.setState( this.getNetworkConfigFromStore() );
  }

  , submitUpdate: function () {
    if ( !_.isEmpty( this.state.locallyModifiedValues ) ) {
      var settings = {
        gateway: {}
        , dns: {
          addresses: []
        }
      };

      if ( !_.isUndefined( this.state.locallyModifiedValues.ipv4 ) ) {
        settings.gateway.ipv4 = this.state.locallyModifiedValues.ipv4;
      }

      if ( !_.isUndefined( this.state.locallyModifiedValues.ipv6 ) ) {
        settings.gateway.ipv6 = this.state.locallyModifiedValues.ipv6;
      }

      if ( !_.isUndefined( this.state.locallyModifiedValues.ns1 ) ) {
        settings.dns.addresses.push( this.state.locallyModifiedValues.ns1 );
      }

      if ( !_.isUndefined( this.state.locallyModifiedValues.ns2 ) ) {
        settings.dns.addresses.push( this.state.locallyModifiedValues.ns2 );
      }

      NM.updateNetworkConfig( settings );
    }
  }

  , editHandleValueChange: function ( key ) {
    var value = this.refs[ key ].getValue();
    var newLocallyModified = this.state.locallyModifiedValues;

    if ( _.isEqual( this.state.remoteState[ key ], value )
        && !_.isUndefined( newLocallyModified[ key ] ) ) {
      delete newLocallyModified[ key ];
    } else {
      newLocallyModified[ key ] = value;
    }

    this.setState({ locallyModifiedValues: newLocallyModified });
  }

  , render: function () {
    var gateway = this.state.networkConfig.gateway || {};
    var addresses = [];
    if ( !_.isUndefined( this.state.networkConfig.dns ) ) {
      addresses = this.state.networkConfig.dns.addresses || [];
    }

    var editButtons =
      <TWBS.ButtonToolbar>
        <TWBS.Button
          className = 'pull-right'
          disabled  = { _.isEmpty( this.state.locallyModifiedValues ) }
          onClick   = { this.submitUpdate }
          bsStyle   = 'info' >
          Save Changes
        </TWBS.Button>
      </TWBS.ButtonToolbar>;

    return (
      <main>
        <div className="network-settings container-fluid">
          { editButtons }
          <form className = "form-horizontal">
            <TWBS.Grid fluid>
              <TWBS.Row>
                <TWBS.Col xs={6}>
                  <TWBS.Input
                    type             = "text"
                    label            = "Hostname"
                    key              = { "hostname" }
                    ref              = "hostname"
                    groupClassName   =
                      { _.has( this.state.locallyModifiedValues["hostname"] )
                      ? "editor-was-modified" : "" }
                    labelClassName   = "col-xs-4"
                    wrapperClassName = "col-xs-8"
                  />
                </TWBS.Col>
                <TWBS.Col xs={6}>
                  <TWBS.Input
                    type             = "text"
                    label            = "Domain"
                    key              = { "domain" }
                    ref              = "domain"
                    groupClassName   =
                      { _.has( this.state.locallyModifiedValues["domain"] )
                      ? "editor-was-modified" : "" }
                    labelClassName   = "col-xs-4"
                    wrapperClassName = "col-xs-8"
                  />
                </TWBS.Col>
              </TWBS.Row>
              <TWBS.Row>
                <TWBS.Col xs={6}>
                  <TWBS.Input
                    type             = "text"
                    label            = "IPv4 Default Gateway"
                    defaultValue     = { gateway.ipv4 || "" }
                    onChange         =
                      { this.editHandleValueChange.bind( null, "ipv4" ) }
                    key              = { "ipv4" }
                    ref              = "ipv4"
                    groupClassName   =
                      { _.has( this.state.locallyModifiedValues["ipv4"] )
                      ? "editor-was-modified" : "" }
                    labelClassName   = "col-xs-4"
                    wrapperClassName = "col-xs-8"
                  />
                </TWBS.Col>
                <TWBS.Col xs={6}>
                  <TWBS.Input
                    type             = "text"
                    label            = "IPv6 Default Gateway"
                    defaultValue     = { gateway.ipv6 || "" }
                    onChange         =
                      { this.editHandleValueChange.bind( null, "ipv6" ) }
                    key              = { "ipv6" }
                    ref              = "ipv6"
                    groupClassName   =
                      { _.has( this.state.locallyModifiedValues["ipv6"] )
                      ? "editor-was-modified" : "" }
                    labelClassName   = "col-xs-4"
                    wrapperClassName = "col-xs-8"
                  />
                </TWBS.Col>
              </TWBS.Row>
              <TWBS.Row>
                <TWBS.Col xs={6}>
                  <TWBS.Input
                    type             = "text"
                    label            = "Nameserver 1"
                    defaultValue     = { addresses[0] || "" }
                    onChange         =
                      { this.editHandleValueChange.bind( null, "ns1" ) }
                    key              = { "ns1" }
                    ref              = "ns1"
                    groupClassName   =
                      { _.has( this.state.locallyModifiedValues["ns1"] )
                      ? "editor-was-modified" : "" }
                    labelClassName   = "col-xs-4"
                    wrapperClassName = "col-xs-8"
                  />
                </TWBS.Col>
                <TWBS.Col xs={6}>
                  <TWBS.Input
                    type             = "text"
                    label            = "Nameserver 2"
                    defaultValue     = { addresses[1] || "" }
                    onChange         =
                      { this.editHandleValueChange.bind( null, "ns2" ) }
                    key              = { "ns2" }
                    ref              = "ns2"
                    groupClassName   =
                      { _.has( this.state.locallyModifiedValues["ns2"] )
                      ? "editor-was-modified" : "" }
                    labelClassName   = "col-xs-4"
                    wrapperClassName = "col-xs-8"
                  />
                </TWBS.Col>
              </TWBS.Row>
            </TWBS.Grid>
          </form>
          { editButtons }
        </div>
      </main>
    );
  }

});

export default NetworkSettings;
