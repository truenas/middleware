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

import GroupView from "./GroupView";
import GroupEdit from "./GroupEdit";

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
