// Group View Component
// ====================
// Handles viewing the properties of a group. Provides no direct editing
// capabilities other than deleting a group completely.


"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import routerShim from "../../../components/mixins/routerShim";
import clientStatus from "../../../components/mixins/clientStatus";

import viewerUtil from "../../../components/Viewer/viewerUtil";

import UsersStore from "../../../stores/UsersStore";

import groupMixins from "../../../components/mixins/groupMixins";
import inputHelpers from "../../../components/mixins/inputHelpers";
import viewerCommon from "../../../components/mixins/viewerCommon";


const GroupView = React.createClass({

  mixins: [ groupMixins
          , viewerCommon ]

  , contextTypes: {
    router: React.PropTypes.func
  }

  , propTypes: {
      item: React.PropTypes.object.isRequired
    }

  , getMembers: function ( groupid ) {
    if ( UsersStore.getUsersByGroup( groupid ) ) {
      return UsersStore.getUsersByGroup( groupid );
    } else {
      return [];
    }
  }

  , createUserDisplayList: function ( groupid ) {
    var listUserItemArray = [];
    var users = this.getMembers( groupid );

    for ( var i = 0; i < users.length; i++ ) {
      listUserItemArray.push(
        <TWBS.ListGroupItem>
          { users[i].username }
        </TWBS.ListGroupItem>
      );
    }

    return listUserItemArray;
  }

  , render: function () {
    var builtInGroupAlert = null;
    var editButtons = null;

    if ( this.props.item["builtIn"] ) {
      builtInGroupAlert = (
        <TWBS.Alert bsStyle   = "info"
                    className = "text-center">
          <b>{"This is a built-in FreeNAS group."}</b>
        </TWBS.Alert>
      );
    }

    editButtons = (
      <TWBS.ButtonToolbar>
        <TWBS.Button
          className = "pull-left"
          disabled  = { this.props.item[ "builtIn" ] }
          onClick   = { this.deleteGroup }
          bsStyle   = "danger" >
            {"Delete Group"}
        </TWBS.Button>
        <TWBS.Button
          className = "pull-right"
          onClick   = { this.props.handleViewChange.bind( null, "edit" ) }
          bsStyle   = "info" >
          {"Edit Group"}
        </TWBS.Button>
      </TWBS.ButtonToolbar>
    );

    return (
      <TWBS.Grid fluid>
        {/* "Edit Group" Button - Top */}
        { editButtons }

        <TWBS.Row>
          <TWBS.Col
            xs={3}
            className="text-center">
            <viewerUtil.ItemIcon
              primaryString  = { this.props.item[ "groupName" ] }
              fallbackString = { this.props.item[ "groupID" ] }
              seedNumber     = { this.props.item[ "groupID" ] } />
          </TWBS.Col>
          <TWBS.Col xs={9}>
            <h3>
              { this.props.item[ "groupName" ] }
            </h3>
            <hr />
          </TWBS.Col>
        </TWBS.Row>

        {/* Shows a warning if the group account is built in */}
        { builtInGroupAlert }

        {/* Primary group data overview */}

        <TWBS.Row>
          <TWBS.Col
            xs      = {2}
            className = "text-muted" >
            <h4 className = "text-muted" >
              { this.props.itemLabels.properties[ "groupID" ] }
            </h4>
          </TWBS.Col>
          <TWBS.Col xs = {10}>
            <h3>
              { this.props.item[ "groupID" ] }
            </h3>
          </TWBS.Col>
        </TWBS.Row>
        <TWBS.Row>
          <TWBS.Col
            xs      = {12}
            className = "text-muted" >
            <h4 className = "text-muted" >
              { "Users" }
            </h4>
            <TWBS.ListGroup>
              { this.createUserDisplayList( this.props.item[ "groupID" ] ) }
            </TWBS.ListGroup>
          </TWBS.Col>
        </TWBS.Row>

      </TWBS.Grid>
    );
  }
});

export default GroupView;
