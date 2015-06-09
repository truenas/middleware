// User Item Template
// ==================
// Handles the viewing and editing of individual user items. Shows a non-editable
// overview of the user account, and mode-switches to a more standard editor
// panel. User is set by providing a route parameter.

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import routerShim from "../../../components/mixins/routerShim";
import clientStatus from "../../../components/mixins/clientStatus";
import viewerCommon from "../../../components/mixins/viewerCommon";

import editorUtil from "../../../components/Viewer/Editor/editorUtil";

import UsersStore from "../../../stores/UsersStore";
import GroupsStore from "../../../stores/GroupsStore";

import UserView from "./UserView";
import UserEdit from "./UserEdit";

// CONTROLLER-VIEW
const UserItem = React.createClass(
  { mixins: [ routerShim, clientStatus, viewerCommon ]

  , getInitialState: function () {
      return (
        { targetUser  : this.getUserFromStore()
        , currentMode : "view"
        , activeRoute : this.getDynamicRoute()
        }
      );
    }

  , componentDidUpdate: function ( prevProps, prevState ) {
      var activeRoute = this.getDynamicRoute();

      if ( activeRoute !== prevState.activeRoute ) {
        this.setState(
          { targetUser  : this.getUserFromStore()
          , currentMode : "view"
          , activeRoute : activeRoute
          }
        );
      }
    }

  , componentDidMount: function () {
      UsersStore.addChangeListener( this.updateUserInState );
    }

  , componentWillUnmount: function () {
      UsersStore.removeChangeListener( this.updateUserInState );
    }

  , getUserFromStore: function () {
      return UsersStore.findUserByKeyValue( this.props.keyUnique, this.getDynamicRoute() );
    }

  , updateUserInState: function () {
      this.setState({ targetUser: this.getUserFromStore() });
    }

  , handleViewChange: function ( nextMode, event ) {
      this.setState({ currentMode: nextMode });
    }

  , render: function () {
      var DisplayComponent = null;
      var processingText   = "";

      if ( this.state.SESSION_AUTHENTICATED && this.state.targetUser ) {

        // PROCESSING OVERLAY
        if ( UsersStore.isLocalTaskPending( this.state.targetUser["id"] ) ) {
          processingText = "Saving changes to '" + this.state.targetUser[ this.props.keyPrimary ] + "'";
        } else if ( UsersStore.isUserUpdatePending( this.state.targetUser["id"] ) ) {
          processingText = "User '" + this.state.targetUser[ this.props.keyPrimary ] + "' was updated remotely.";
        }

        // DISPLAY COMPONENT
        var childProps = {
            handleViewChange : this.handleViewChange
          , item             : this.state.targetUser
        };

        switch ( this.state.currentMode ) {
          default:
          case "view":
            DisplayComponent = <UserView { ...this.getRequiredProps() } { ...childProps } />;
            break;

          case "edit":
            DisplayComponent = <UserEdit { ...this.getRequiredProps() } { ...childProps } />;
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

export default UserItem;
