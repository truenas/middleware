// Group Item Template
// ==================
// Handles the viewing and editing of individual group items. Shows a non-editable
// overview of the group, and mode-switches to a more standard editor panel.
// Group is set by providing a route parameter.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import routerShim from "../../../components/mixins/routerShim";
import clientStatus from "../../../components/mixins/clientStatus";

import viewerUtil from "../../../components/Viewer/viewerUtil";
import editorUtil from "../../../components/Viewer/Editor/editorUtil";

import GroupsMiddleware from "../../../middleware/GroupsMiddleware";
import GroupsStore from "../../../stores/GroupsStore";

import UsersStore from "../../../stores/UsersStore";

import groupMixins from "../../../components/mixins/groupMixins";
import inputHelpers from "../../../components/mixins/inputHelpers";
import viewerCommon from "../../../components/mixins/viewerCommon";

import GroupEdit from "./GroupEdit";

const GroupView = React.createClass({

    mixins: [   groupMixins
              , viewerCommon ]

  , contextTypes: {
      router: React.PropTypes.func
  }

  , propTypes: {
      item: React.PropTypes.object.isRequired
    }

  , getMembers: function( groupid ) {
    if ( UsersStore.getUsersByGroup( groupid ) ) {
      return UsersStore.getUsersByGroup( groupid );
    } else {
      return [];
    }
  }

  , createUserDisplayList: function( groupid ) {
      var listUserItemArray = [];
      var users = this.getMembers( groupid );

      for (var i = 0; i < users.length; i++) {
         listUserItemArray.push(<TWBS.ListGroupItem>{ users[i].username }</TWBS.ListGroupItem>);
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
          <TWBS.Button className = "pull-left"
                       disabled  = { this.props.item["builtIn"] }
                       onClick   = { this.deleteGroup }
                       bsStyle   = "danger" >{"Delete Group"}</TWBS.Button>
          <TWBS.Button className = "pull-right"
                       onClick   = { this.props.handleViewChange.bind(null, "edit") }
                       bsStyle   = "info" >{"Edit Group"}</TWBS.Button>
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
              { this.props.itemLabels[ "groupID "] }
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

// CONTROLLER-VIEW
const GroupItem = React.createClass({

      mixins: [ routerShim, clientStatus, viewerCommon ]

    , getInitialState: function () {
        return {
            targetGroup : this.getGroupFromStore()
          , currentMode : "view"
          , activeRoute : this.getDynamicRoute()
        };
      }

    , componentDidUpdate: function( prevProps, prevState ) {
        var activeRoute = this.getDynamicRoute();

        if ( activeRoute !== prevState.activeRoute ) {
          this.setState({
              targetGroup  : this.getGroupFromStore()
            , currentMode : "view"
            , activeRoute : activeRoute
          });
        }
      }

    , componentDidMount: function () {
        GroupsStore.addChangeListener( this.updateGroupInState );
      }

    , componentWillUnmount: function () {
        GroupsStore.removeChangeListener( this.updateGroupInState );
      }

    , getGroupFromStore: function () {
        return GroupsStore.findGroupByKeyValue( this.props.keyUnique, this.getDynamicRoute() );
      }

    , updateGroupInState: function () {
        this.setState({ targetGroup: this.getGroupFromStore() });
      }

    , handleViewChange: function( nextMode, event ) {
        this.setState({ currentMode: nextMode });
      }

    , render: function () {
        var DisplayComponent = null;
        var processingText = "";

        if ( this.state.SESSION_AUTHENTICATED && this.state.targetGroup ) {

          // PROCESSING OVERLAY
          if ( GroupsStore.isLocalTaskPending( this.state.targetGroup["groupID"] ) ) {
            processingText = "Saving changes to '" + this.state.targetGroup[ this.props.viewData.format["primaryKey" ] ] + "'";
          } else if (GroupsStore.isGroupUpdatePending( this.state.targetGroup[ "groupID"] ) ) {
            processingText = "Group '" + this.state.targetGroup[ this.props.keyPrimary ] + "' was updated remotely.";
          }

          // DISPLAY COMPONENT
          let childProps = { handleViewChange : this.handleViewChange
                           , item             : this.state.targetGroup
                           };

          switch( this.state.currentMode ) {
            default:
            case "view":
              DisplayComponent = <GroupView { ...childProps }
                                            { ...this.getRequiredProps() } />;
              break;
            case "edit":
              DisplayComponent = <GroupEdit { ...childProps }
                                            { ...this.getRequiredProps() } />;
              break;
          }
        }

        return (
          <div className="viewer-item-info">

            {/* Overlay to block interaction while tasks or updates are processing */}
            <editorUtil.updateOverlay updateString={ processingText } />

            { DisplayComponent }

          </div>
        );
      }
});

export default GroupItem;
