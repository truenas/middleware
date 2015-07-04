// Network
// =======

"use strict";

import React from "react";
import TWBS from "react-bootstrap"
import _ from "lodash";

import Router from "react-router";

import NM from "../middleware/NetworkConfigMiddleware";
import NS from "../stores/NetworkConfigStore";

import IM from "../middleware/InterfacesMiddleware";
import IS from "../stores/InterfacesStore";

import SM from "../middleware/SystemMiddleware";
import SS from "../stores/SystemStore";

import Icon from "../components/Icon";

/**
 * The collapsible section.
 */
var NetworkSection = React.createClass(
  { displayName: "Networks"

  , getInitialState: function () {
    return {
      isCollapsed: false
    };
  }

  /**
   * Toggle section.
   */
  , toggleSection: function () {
    this.setState({
      isCollapsed: !this.state.isCollapsed
    });
  }

  , render: function () {

    var sectionClass =
      ( this.state.isCollapsed ? "collapsed " : "" ) + "section";

    var iconType = this.state.isCollapsed ? "chevron-right" : "chevron-down";

    var headerButtons = "";
    if ( !_.isUndefined( this.props.onSave ) ) {
      headerButtons =
        <div className="header-buttons">
          <TWBS.Button
            onClick   = { this.props.onSave }
            bsStyle   = "primary">
            <Icon glyph="check" /> Save
          </TWBS.Button>
        </div>;
    }

    return (
      <div className={ sectionClass }>
        <div className="section-header" onClick={ this.toggleSection }>
          <div className="header-text">
            <Icon glyph={ iconType } />
            { this.props.header }
          </div>
          { headerButtons }
        </div>
        <div className="section-body">
          { this.props.children }
        </div>
      </div>
    );
  }
});

/**
 * The individual interface widget.
 */
var InterfaceWidget = React.createClass({

  getInitialState: function () {
    // Default interface data.
    var defaultInterface = {
      name: ""
      , dhcp: false
      , status: {
        flags: []
        , aliases: []
      }
    };

    var interfaceData =
      _.defaults( this.props.interfaceData, defaultInterface );

    return {
      isCollapsed     : true
      , interfaceData : interfaceData
      , editData      : _.cloneDeep( interfaceData )
    };
  }
  /**
   * Retrieve the list of aliases of a specific family.
   * @param  {String} family "LINK" for MAC, "INET" for IPv4, "INET6" for IPv6.
   * @return {Array} An array of aliases(String).
   */
  , getAliases: function ( family ) {
      var aliases = [];
      _.each( this.state.interfaceData.status.aliases, function ( alias ) {
        if ( alias.family === family ) {
          aliases.push(
            alias.address
            + ( !_.isUndefined( alias.netmask ) ? "/" + alias.netmask : "" )
            + ( !_.isUndefined( alias.broadcast )
              ? " (" + alias.broadcast +  ")" : "" )
          );
        }
      });
      return aliases;
    }

  /**
   * Update the interface status (Up or down the interface).
   */
  , updateStatus: function () {
      var isUp = _.includes( this.state.interfaceData.status.flags, "UP" );
      if ( isUp ) {
        IM.downInterface( this.state.interfaceData.name );
      } else {
        IM.upInterface( this.state.interfaceData.name );
      }
    }

  /**
   * Expand the edit view.
   */
  , expandEdit: function () {
      this.setState({
        isCollapsed: false
        , editData: _.cloneDeep( this.state.interfaceData )
      });
    }

  /**
   * Collapse the edit view.
   */
  , cancelEdit: function () {
      this.setState({
        isCollapsed: true
      });
    }

  /**
   * Save the changes.
   */
  , saveInterface: function () {
      IM.configureInterface(
        this.state.interfaceData.name
        , {
          dhcp: this.state.editData.dhcp
        }
      );
    }

  /**
   * Handle updates on the UI inputs.
   * @param  {String} key The key of the field updated.
   * @param  {Object} evt
   */
  , handleChange: function ( key, evt ) {
      switch ( key ) {
        case "dhcp":
          var editData = this.state.editData;
          editData.dhcp = evt.target.checked;
          this.setState({
            editData: editData
          });
          break;
      }
    }

  , render: function () {
      var _interface = this.state.interfaceData;

      var widgetClass = ( this.state.isCollapsed ? "collapsed " : "" )
                        + "interface-widget";

      // Get the interface status.
      var isUp = _.includes( _interface.status.flags, "UP" );
      var statusClass = ( isUp ? "status-up" : "status-down" )
                        + " interface-status";
      var statusTitle = isUp ? "The interface is up."
                        : "The interface is down.";

      // Get the interface aliases.
      var macAddresses = this.getAliases( "LINK" );
      var macPart = "";
      if ( macAddresses.length ) {
        macPart =
          <div className="interface-address">
            <label>MAC Address</label>
            <span>{ macAddresses.join( "<br/>" ) }</span>
          </div>;
      }

      var ipv4Addresses = this.getAliases( "INET" );
      var ipv4Part = "";
      if ( ipv4Addresses.length ) {
        ipv4Part =
          <div className="interface-address">
            <label>IPv4 Address</label>
            <span>{ ipv4Addresses.join( "<br/>" ) }</span>
          </div>;
      }

      var ipv6Addresses = this.getAliases( "INET6" );
      var ipv6Part = "";
      if ( ipv6Addresses.length ) {
        ipv6Part =
          <div className="interface-address">
            <label>IPv6 Address</label>
            <span>{ ipv6Addresses.join( "<br/>" ) }</span>
          </div>;
      }

      return (
        <div className={ widgetClass }>
          <div className="widget-header">
            <div className="upper-section">
              <div className={ statusClass } title={ statusTitle }>
              </div>
              <div className="interface-name">
                { _interface.name }
              </div>
              <div
                className="interface-dhcp"
                title={ _interface.dhcp
                      ? "DHCP enabled" : "DHCP disabled" }>
                <Icon glyph={ _interface.dhcp
                            ? "check text-primary" : "times text-muted" } />
              </div>
              <div className="interface-type">
                <small>{ _interface.type }</small>
              </div>
            </div>
            { macPart }
            { ipv4Part }
            { ipv6Part }
            <div className="bottom-section">
              <TWBS.Button
                onClick   = { this.updateStatus }
                className = "pull-left"
                bsStyle   = "danger"
                bsSize    = "small">
                <Icon glyph="power-off" />&nbsp;
                { isUp ? "Down Interface" : "Up Interface" }
              </TWBS.Button>
              <TWBS.Button
                onClick   = { this.expandEdit }
                className =
                  { ( this.state.isCollapsed ? "" : "hidden " ) + "pull-right" }
                bsStyle   = "primary"
                bsSize    = "small">
                <Icon glyph="pencil-square-o" /> Edit
              </TWBS.Button>
            </div>
          </div>
          <div className="widget-body">
            <div className="row">
              <div className="col-sm-3">
                <label>DHCP</label>
              </div>
              <div className="col-sm-9">
                <TWBS.Input
                  type      = "checkbox"
                  label     = "Enabled"
                  checked   = { this.state.editData.dhcp }
                  onChange  = { this.handleChange.bind( this, "dhcp" ) } />
              </div>
            </div>
            <div className="bottom-section">
              <TWBS.Button
                onClick   = { this.cancelEdit }
                className = "pull-left"
                bsStyle   = "info"
                bsSize    = "small">
                <Icon glyph="times" /> Cancel
              </TWBS.Button>
              <TWBS.Button
                onClick   = { this.saveInterface }
                className = "pull-right"
                bsStyle   = "primary"
                bsSize    = "small">
                <Icon glyph="check" /> Save
              </TWBS.Button>
            </div>
          </div>
        </div>
      );
    }
});

const Network = React.createClass({

  displayName: "Network"
  , previousSSUpdateStatus: false
  , previousNSUpdateStatus: false

  , getInitialState: function () {
    return _.assign( this.getNetworkConfigFromStore()
                    , this.getSystemGeneralConfigFromStore()
                    , this.getInterfaceListFromStore()
                    , {
                      newDnsServer: ""
                    } );
  }

  , componentDidMount: function () {
    NS.addChangeListener( this.onNetworkConfigChange );
    NM.requestNetworkConfig();
    NM.subscribe( this.constructor.displayName );

    IS.addChangeListener( this.onInterfaceListChange );
    IM.requestInterfacesList();

    SS.addChangeListener( this.onSystemGeneralConfigChange );
    SM.requestSystemGeneralConfig();
    SM.subscribe( this.constructor.displayName );
  }

  , componentWillUnmount: function () {
    NS.removeChangeListener( this.onNetworkConfigChange );
    NM.unsubscribe( this.constructor.displayName );

    IS.removeChangeListener( this.onInterfaceListChange );

    SS.removeChangeListener( this.onSystemGeneralConfigChange );
    SM.unsubscribe( this.constructor.displayName );
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
      networkConfig       : networkConfig
      , oldNetworkConfig  : _.cloneDeep( networkConfig )
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
      systemGeneralConfig       : systemGeneralConfig
      , oldSystemGeneralConfig  : _.cloneDeep( systemGeneralConfig )
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

      case "newDnsServer":
        this.setState({
          newDnsServer: evt.target.value
        });
        break;
    }
  }

  /**
   * Save the changes on the General section.
   */
  , saveGeneralConfig: function ( evt ) {
    evt.stopPropagation();

    // No need to call the API if there are no changes.
    if ( !_.isEqual( this.state.systemGeneralConfig
                    , this.state.oldSystemGeneralConfig ) ) {
      SM.updateSystemGeneralConfig( this.state.systemGeneralConfig );

      this.setState({
        oldSystemGeneralConfig: _.cloneDeep( this.state.systemGeneralConfig )
      });
    }

    if ( !_.isEqual( this.state.networkConfig
                    , this.state.oldNetworkConfig ) ) {
      NM.updateNetworkConfig( this.state.networkConfig );

      this.setState({
        oldNetworkConfig: _.cloneDeep( this.state.networkConfig )
      });
    }
  }

  /**
   * Add a new DNS server.
   */
  , addNewDnsServer: function () {
    if ( this.state.newDnsServer === "" ) {
      // No need to add an empty server.
      return;
    }

    var networkConfig = this.state.networkConfig;
    if ( _.includes( networkConfig.dns.servers, this.state.newDnsServer ) ) {
      // No need to add a duplicate entry.
      return;
    }

    // Append a new DNS server to the list.
    networkConfig.dns.servers.push( this.state.newDnsServer );

    // Reset the input value.
    this.setState({
      networkConfig: networkConfig
      , newDnsServer: ""
    });
  }

  /**
   * Delete a DNS server.
   * @param  {int} index The index of server to delete in the dns.servers array.
   */
  , deleteDnsServer: function ( index ) {
    var networkConfig = this.state.networkConfig;
    networkConfig.dns.servers.splice( index, 1 );
    this.setState({
      networkConfig: networkConfig
    });
  }

  , render: function () {
    // Compile the DNS server list.
    var dnsNodes =
      <li>
        <div className="dns-server">
          <em>No DNS servers configured</em>
        </div>
      </li>;

    if ( this.state.networkConfig.dns.servers.length ) {
      var that = this;
      dnsNodes = _.map(
        this.state.networkConfig.dns.servers
        , function ( server, index ) {
          return (
            <li key={ index }>
              <div className="dns-server">
                {server}
              </div>
              <TWBS.Button
                onClick = { that.deleteDnsServer.bind( null, index ) }
                bsStyle = "danger"
                bsSize  = "small"
                title   = "Delete Server">
                <Icon glyph="times" />
              </TWBS.Button>
            </li>
          );
        }
      );
    }

    dnsNodes =
      <ul className="dns-server-list">
        {dnsNodes}
      </ul>;

    var interfaceWidgets =
      <div className="text-center">
        <em>No interfaces found.</em>
      </div>;

    if ( this.state.interfacesList.length ) {
      interfaceWidgets = _.map(
        this.state.interfacesList
        , function ( _interface, index ) {
            return (
              <div className="col-sm-3" key={ index }>
                <InterfaceWidget interfaceData={_interface} />
              </div>
            );
          }
        );
    }

    // Show the save status message.
    var alert = "";
    var currentSSUpdateStatus = SS.isUpdating();
    var currentNSUpdateStatus = NS.isUpdating();
    if ( currentSSUpdateStatus || currentNSUpdateStatus ) {
      alert =
        <div className="text-center">
          <TWBS.Alert bsStyle="info">
            Saving changes...
          </TWBS.Alert>
        </div>;
    } else if ( this.previousSSUpdateStatus || this.previousNSUpdateStatus ) {
      alert =
        <div className="text-center">
          <TWBS.Alert bsStyle="success">
            Saved successfully.
          </TWBS.Alert>
        </div>;
    }
    this.previousSSUpdateStatus = currentSSUpdateStatus;
    this.previousNSUpdateStatus = currentNSUpdateStatus;

    return (
      <main>
        <div className="network-overview container-fluid">
          <NetworkSection header="General" onSave={ this.saveGeneralConfig }>
            <div className="row">
              { alert }
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
              <div className="col-sm-6">
                <div className="form-group">
                  <label className="col-xs-3">DNS Server</label>
                  <div className="col-xs-9">
                    {dnsNodes}
                    <div className="row">
                      <div className="col-sm-9">
                        <TWBS.Input
                          type        = "text"
                          value       = {this.state.newDnsServer}
                          onChange    =
                            {this.handleChange.bind( this, "newDnsServer" )}
                          placeholder = "Enter the new DNS server" />
                      </div>
                      <div className="col-sm-3 text-right">
                        <TWBS.Button
                          onClick = { this.addNewDnsServer }
                          bsStyle = "primary"
                          bsSize  = "small"
                          title   = "Add New DNS Server">
                          <Icon glyph="plus" />
                        </TWBS.Button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </NetworkSection>
          <NetworkSection header="Interfaces">
            <div className="row">
              { interfaceWidgets }
            </div>
          </NetworkSection>
        </div>
      </main>
    );
  }

});

export default Network;
