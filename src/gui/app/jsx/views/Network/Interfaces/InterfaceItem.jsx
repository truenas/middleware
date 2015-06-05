// Interface Item
// ==============
// Handles viewing and and changing of network interfaces.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import routerShim from "../../../components/mixins/routerShim";
import clientStatus from "../../../components/mixins/clientStatus";

import viewerUtil from "../../../components/Viewer/viewerUtil";

import IS from "../../../stores/InterfacesStore";
import IM from "../../../middleware/InterfacesMiddleware"

import Icon from "../../../components/Icon";

import InterfaceEdit from "./InterfaceEdit";

const InterfaceView = React.createClass({

  propTypes: {
    item: React.PropTypes.object.isRequired
    , handleViewChange: React.PropTypes.func.isRequired
    , viewData: React.PropTypes.object.isRequired
    , upInterface: React.PropTypes.func
    , downInterface: React.PropTypes.func
  }

  // Map an array of aliases into an array of ListGroupItems representing all
  // aliases of 'family' (ie INET, INET6). Not providing a family will  map all
  // the aliases.
  , createAliasDisplayList: function ( family ) {
    let aliasDisplayItems = null;

    // Only do anything if the interface exists and there are any aliases.
    // The first check should never fail, but I've said that before and
    // regretted it.
    if ( !_.isEmpty( this.props.item )
      && !_.isEmpty( this.props.item.status ) ) {
      aliasDisplayItems =
        _.map( this.props.item.status.aliases
             , function mapAliasesToList ( alias, key ) {

               // Only return items for aliases matching the given family.
               if ( family === "INET" && alias.family === "INET" ) {
                 return ( this.createAliasDisplayItem( alias ) );
               } else if ( family === "INET6" && alias.family === "INET6" ) {
                 return ( this.createAliasDisplayItem( alias ) );
               // If no family was specified or the family was unrecognized,
               // create a list item for every alias. This item is different
               // because we can't make certain assumptions.
               } else if ( family !== "INET" && family !== "INET6" ) {
                 return (
                   <TWBS.ListGroupItem>
                     { "Link Type: " + family }
                     <br />
                     <br />
                     { "Address: " }
                     <br />
                     <strong>{ alias.address }</strong>
                   </TWBS.ListGroupItem>
                 )
               }
             }
             , this )
      return ( _.compact( aliasDisplayItems ) )
    } else {
      return null;
    }

  }

  // Create the individual items for createAliasDisplayList.
  , createAliasDisplayItem: function ( alias ) {
    return (
      <TWBS.ListGroupItem className = "aliasDisplayItem">
        <span className = "aliasItemIP">
          <strong>{ alias.address }</strong>
        </span>
        <span className = "aliasItemNetmask">
          <em>{ "/" + alias.netmask
              + " (" + alias.broadcast
              + ")" }
          </em>
        </span>
      </TWBS.ListGroupItem>
    )
  }

  , render: function () {

    let downInterfaceButton =
      ( <TWBS.Button
          className = "pull-right"
          onClick = { this.props.downInterface }
          bsStyle = "primary">
          { "Down Interface" }
      </TWBS.Button>
    );

    let upInterfaceButton =
      ( <TWBS.Button
          className = "pull-right"
          onClick = { this.props.upInterface }
          bsStyle = "primary">
          { "Up Interface" }
       </TWBS.Button>
      );

    let configureButtons = (
      <TWBS.ButtonToolbar>
        { _.includes( this.props.item[ "status" ][ "flags" ]
                    , "UP" )
        ? downInterfaceButton
        : upInterfaceButton
        }
        <TWBS.Button
          className = "pull-right"
          onClick = { this.props.handleViewChange.bind( null, "edit" ) }
          bsStyle = "primary">
          { "Configure Interface" }
        </TWBS.Button>
      </TWBS.ButtonToolbar>
    );

    let interfaceName = (
      <TWBS.Panel>
        { "Interface Name: " }
        <strong>{ this.props.item[ "name" ] }</strong>
      </TWBS.Panel>
    );

    let linkAddress = (
      <TWBS.Panel>
        { "MAC Address: " }
        <strong>{ this.props.item[ "status" ][ "link-address" ] }</strong>
      </TWBS.Panel>
    );

    let dhcpConfigured = (
      <TWBS.Panel>
        { "DHCP Configured: " }
        <Icon glyph = { this.props.item[ "dhcp" ]
                      ? "check text-primary"
                      : "times text-muted"
                      } />
      </TWBS.Panel>
    )

    let interfaceType = (
      <TWBS.Panel>
        { "Interface Type: " }
        <strong>{ this.props.item[ "type" ] }</strong>
      </TWBS.Panel>
    )

    return (
      <TWBS.Grid fluid>
        <TWBS.Row>
          <TWBS.Col xs = {12}>
            { configureButtons }
          </TWBS.Col>
        </TWBS.Row>
        <TWBS.Row>
          <TWBS.Col xs = {6}>
            { interfaceName }
          </TWBS.Col>
          <TWBS.Col xs = {6}>
            { linkAddress }
          </TWBS.Col>
        </TWBS.Row>
        <TWBS.Row>
          <TWBS.Col xs = {6}>
            { dhcpConfigured }
          </TWBS.Col>
          <TWBS.Col xs = {6}>
            { interfaceType }
          </TWBS.Col>
        </TWBS.Row>
        <TWBS.Row>
          <TWBS.Col xs = {6} >
            <h4>{ "IPv4 Aliases" }</h4>
            <TWBS.PanelGroup>

              <TWBS.Panel>
                <TWBS.ListGroup fill className ="aliasDisplayList">
                  { this.createAliasDisplayList( "INET" ) }
                </TWBS.ListGroup>
              </TWBS.Panel>
            </TWBS.PanelGroup>
          </TWBS.Col>
          <TWBS.Col xs = {6} >
            <h4>{ "IPv6 Aliases" }</h4>
            <TWBS.PanelGroup>
              <TWBS.Panel>
                <TWBS.ListGroup fill className ="aliasDisplayList">
                  { this.createAliasDisplayList( "INET6" ) }
                </TWBS.ListGroup>
              </TWBS.Panel>
            </TWBS.PanelGroup>
          </TWBS.Col>
        </TWBS.Row>
      </TWBS.Grid>
    );
  }

});

const InterfaceItem = React.createClass({

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
      IS.addChangeListener( this.updateInterfaceInState );
    }

  , componentWillUnmount: function () {
      IS.removeChangeListener( this.updateInterfaceInState );
    }

  , getInterfaceFromStore: function () {
      let format = this.props.viewData.format;
      return IS.findInterfaceByKeyValue( format["selectionKey"]
                                       , this.getDynamicRoute() );
    }

  , updateInterfaceInState: function () {
      this.setState({ targetInterface: this.getInterfaceFromStore() });
    }

  , downInterface: function () {
    IM.downInterface( this.state.targetInterface[ "name" ] );
  }

  , upInterface: function () {
    IM.upInterface( this.state.targetInterface[ "name" ] );
  }

  , handleViewChange: function ( nextMode, event ) {
      this.setState({ currentMode: nextMode });
    }

  , render: function () {
    let DisplayComponent = null;

    if ( this.state.SESSION_AUTHENTICATED && this.state.targetInterface ) {
      var childProps = {
        handleViewChange: this.handleViewChange
        , item: this.state.targetInterface
        , viewData: this.props.viewData
        , upInterface: this.upInterface
        , downInterface: this.downInterface
      };

      switch ( this.state.currentMode ) {
        default:
        case "view":
          DisplayComponent = <InterfaceView {...childProps} />;
          break;
        case "edit":
          DisplayComponent = <InterfaceEdit {...childProps} />;
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

export default InterfaceItem;
