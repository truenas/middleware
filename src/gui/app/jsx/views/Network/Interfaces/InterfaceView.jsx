// INTERFACE VIEW TEMPLATE
// =======================
// The initial view of an interface, showing up-front information and status.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import interfaceMixins from "../../../components/mixins/interfaceMixins";
import viewerCommon from "../../../components/mixins/viewerCommon";

import Icon from "../../../components/Icon";

const InterfaceView = React.createClass(
  { mixins: [ interfaceMixins, viewerCommon ]

  , propTypes: {
      item                : React.PropTypes.object.isRequired
      , handleViewChange  : React.PropTypes.func.isRequired
      , upInterface       : React.PropTypes.func.isRequired
      , downInterface     : React.PropTypes.func.isRequired
    }

  /**
   * Map an array of aliases into an array of ListGroupItems representing all
   * aliases of 'family' (i.e. INET, INET6). Not providing a family will map all
   * the aliases.
   * @param  {String} family
   * @return {Array}
   */
  , createAliasDisplayList: function ( family ) {
      // Only do anything if the interface exists and there are any aliases.
      if ( _.isEmpty( this.props.item )
        || _.isEmpty( this.props.item.status ) ) {
        return [];
      }

      var aliasDisplayItems = [];
      _.each( this.props.item.status.aliases , function ( alias ) {
          // If no family was specified or the family was unrecognized, create
          // a list item for every alias. This item is different because
          // we can't make certain assumptions.
          if ( _.isUndefined(family)
            || ( family !== 'INET' && family !== 'INET6' ) ) {
            aliasDisplayItems.push(
              <TWBS.ListGroupItem>
                { "Link Type: " + family }
                <br/>
                <br/>
                { "Address:  " }
                <br/>
                <strong>{ alias.address }</strong>
              </TWBS.ListGroupItem>
            );
          } else if ( family === alias.family ) {
            aliasDisplayItems.push( this.createAliasDisplayItem( alias ) );
          }
      }, this);
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
      var downButton = (
        <TWBS.Button
          className = 'pull-right'
          onClick   = { this.props.downInterface }
          bsStyle   = 'primary'>
          { 'Down Interface' }
        </TWBS.Button>
      );

      var upButton = (
        <TWBS.Button
          className = 'pull-right'
          onClick   = { this.props.upInterface }
          bsStyle   = 'primary'>
          { 'Up Interface' }
        </TWBS.Button>
      );

      var configButtons = (
        <TWBS.ButtonToolbar>
          { _.includes( this.props.item.status.flags, 'UP' )
            ? downButton : upButton }
          <TWBS.Button
            className = 'pull-right'
            onClick   = { this.props.handleViewChange.bind( null, 'edit' ) }
            bsStyle   = 'primary'>
            { "Configure Interface" }
          </TWBS.Button>
        </TWBS.ButtonToolbar>
      );

      return (
        <TWBS.Grid fluid>
          <TWBS.Row>
            <TWBS.Col xs={12}>
              { configButtons }
            </TWBS.Col>
          </TWBS.Row>
          <TWBS.Row>
            <TWBS.Col xs={6}>
              <label>Interface Name</label>
              <div>{ this.props.item.name }</div>
            </TWBS.Col>
            <TWBS.Col xs={6}>
              <label>MAC Address</label>
              <div>{ this.props.item.status['link-address'] }</div>
            </TWBS.Col>
          </TWBS.Row>
          <TWBS.Row>
            <TWBS.Col xs={6}>
              <label>DHCP Configured</label>
              <div>
                <Icon glyph={ this.props.item.dhcp
                            ? 'check text-primary' : 'times text-muted' } />
              </div>
            </TWBS.Col>
            <TWBS.Col xs={6}>
              <label>Interface Type</label>
              <div>{ this.props.item.type }</div>
            </TWBS.Col>
          </TWBS.Row>
          <TWBS.Row>
            <TWBS.Col xs={6}>
              <TWBS.Panel header='IPv4 Aliases'>
                <TWBS.ListGroup fill className='alias-display-list'>
                  { this.createAliasDisplayList( 'INET' ) }
                </TWBS.ListGroup>
              </TWBS.Panel>
            </TWBS.Col>
            <TWBS.Col xs={6}>
              <TWBS.Panel header='IPv6 Aliases'>
                <TWBS.ListGroup fill className='alias-display-list'>
                  { this.createAliasDisplayList( 'INET6' ) }
                </TWBS.ListGroup>
              </TWBS.Panel>
            </TWBS.Col>
          </TWBS.Row>
        </TWBS.Grid>
      );
    }
  }
);

export default InterfaceView;
