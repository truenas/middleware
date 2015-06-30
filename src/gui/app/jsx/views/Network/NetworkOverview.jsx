// Network Configuration Overview
// ==============================

"use strict";

var componentLongName = "NetworkOverview";

import React from "react/addons";
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

  mixins: [ React.addons.LinkedStateMixin ]

  , getInitialState: function () {
    return this.getNetworkConfigFromStore();
  }

  , componentDidMount: function () {
    NS.addChangeListener( this.handleConfigChange );
    NM.requestNetworkConfig();

    IS.addChangeListener( this.handleConfigChange );
    IM.requestInterfacesList();

    SS.addChangeListener( this.handleConfigChange );
    SM.requestSystemGeneralConfig();
  }

  , componentWillUnmount: function () {
    NS.removeChangeListener( this.handleConfigChange );

    IS.removeChangeListener( this.handleConfigChange );

    SS.removeChangeListener( this.handleConfigChange );
  }

  , getNetworkConfigFromStore: function () {
    var networkConfig = NS.getNetworkConfig();
    var systemGeneralConfig = SS.getSystemGeneralConfig();
    var gateway = networkConfig.gateway || {};

    return {
      interfacesList      : IS.getAllInterfaces()
      , hostname  : systemGeneralConfig.hostname || ""
      , ipv4      : gateway.ipv4 || ""
      , ipv6      : gateway.ipv6 || ""
    };
  }

  , handleConfigChange: function () {
    this.setState( this.getNetworkConfigFromStore() );
  }

  , saveGeneralConfig: function () {
    var networkConfig = {
      gateway: {
        ipv4    : this.state.ipv4
        , ipv6  : this.state.ipv6
      }
    };

    var systemGeneralConfig = {
      hostname: this.state.hostname
    };

    NM.updateNetworkConfig( networkConfig );
    SM.updateSystemGeneralConfig( systemGeneralConfig );
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
                        valueLink   = {this.linkState( "hostname" )}
                        placeholder = "Hostname" />
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="col-xs-3">IPv4 Default Gateway</label>
                    <div className="col-xs-9">
                      <TWBS.Input
                        type        = "text"
                        valueLink   = {this.linkState( "ipv4" )}
                        placeholder = "IPv4 Default Gateway" />
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="col-xs-3">IPv6 Default Gateway</label>
                    <div className="col-xs-9">
                      <TWBS.Input
                        type        = "text"
                        valueLink   = {this.linkState( "ipv6" )}
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
