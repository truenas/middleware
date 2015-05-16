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

      if ( this.props.item["builtin"] ) {
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
                       disabled  = { this.props.item["builtin"] }
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
          <TWBS.Col xs={3}
                    className="text-center">
            <viewerUtil.ItemIcon primaryString  = { this.props.item["name"] }
                                 fallbackString = { this.props.item["id"] }
                                 seedNumber     = { this.props.item["id"] } />
          </TWBS.Col>
          <TWBS.Col xs={9}>
            <h3>{ this.props.item["name"] }</h3>
            <hr />
          </TWBS.Col>
        </TWBS.Row>

          {/* Shows a warning if the group account is built in */}
          { builtInGroupAlert }

          {/* Primary group data overview */}

        <TWBS.Row>
	  <TWBS.Col xs      = {2}
	            className = "text-muted" >
	            <h4 className = "text-muted" >{ "Group ID" }</h4>
	  </TWBS.Col>
          <TWBS.Col xs = {10}>
		    <h3>{this.props.item["id"]}</h3>
	  </TWBS.Col>
        </TWBS.Row>
	<TWBS.Row>
	  <TWBS.Col xs      = {12}
	            className = "text-muted" >
	            <h4 className = "text-muted" >{ "Users" }</h4>
                       <TWBS.ListGroup>
                          { this.createUserDisplayList( this.props.item["id"] ) }
		       </TWBS.ListGroup>
          </TWBS.Col>
        </TWBS.Row>

          {/* "Edit Group" Button - Bottom */}
          { editButtons }

        </TWBS.Grid>
      );
  }
});

// EDITOR PANE
const GroupEdit = React.createClass({

    mixins: [  inputHelpers
              , groupMixins
              , viewerCommon ]

  , contextTypes: {
        router: React.PropTypes.func
    }

  , propTypes: {
      item: React.PropTypes.object.isRequired
    }

  , getInitialState: function () {
      var remoteState = this.setRemoteState( this.props );

      return {
          locallyModifiedValues  : {}
        , remotelyModifiedValues : {}
        , remoteState            : remoteState
        , mixedValues            : this.props.item
        , lastSentValues         : {}
        , dataKeys               : this.props.viewData["format"]["dataKeys"]
      };
    }

  , componentWillRecieveProps: function( nextProps ) {
      var newRemoteModified = {};
      var newLocallyModified = {};

      // remotelyModifiedValues represents everything that's changed remotely
      // since the view was opened. This is the difference between the newly arriving
      // props and the initial ones. Read-only and unknown values are ignored.
      // TODO: Use this to show alerts for remote changes on sections the local
      // administrator is working on.
      var mismatchedRemoteFields = _.pick(nextProps.item, function( value, key ) {
        return _.isEqual( this.state.remoteState[ key ], value );
      }, this);

      newRemoteModified = this.removeReadOnlyFields( mismatchedRemoteFields, nextProps.viewData["format"]["dataKeys"]);

      // remoteState records the item as it was when the view was first
      // opened. This is used to mark changes that have occurred remotely since
      // the user began editing.
      // It is important to know if the incoming change resulted from a call
      // made by the local administrator. When this happens, we reset the
      // remoteState to get rid of remote edit markers, as the local version
      // has thus become authoritative.
      // We check this by comparing the incoming changes (newRemoteModified) to the
      // last request sent (this.state.lastSentValues). If this check succeeds,
      // we reset newLocallyModified and newRemoteModified, as there are no longer
      // any remote or local changes to record.
      // TODO: Do this in a deterministic way, instead of relying on comparing
      // values.
      if (_.isEqual(this.state.lastSentValues, newRemoteModified)){
          newRemoteModified  = {};
          newLocallyModified = {};
          this.setState ({
              remoteState           : this.setRemoteState(nextProps)
            , locallyModifiedValues : newLocallyModified
          });
      }

      this.setState({
          remotelyModifiedValues : newRemoteModified
      });
    }

  , submitGroupUpdate: function () {
      var valuesToSend = this.removeReadOnlyFields( this.state.locallyModifiedValues, this.state.dataKeys );

      // Only bother to submit an update if there is anything to update.
      if ( !_.isEmpty( valuesToSend ) ){
        GroupsMiddleware.updateGroup( this.props.item["id"], valuesToSend, this.submissionRedirect( valuesToSend ) );
        // Save a record of the last changes we sent.
        this.setState({
            lastSentValues : valuesToSend
        });
      } else {
          console.warn( "Attempted to send a Group update with no valid fields." );
      }
    }

  , render: function () {
      var builtInGroupAlert = null;
      var editButtons       = null;
      var inputForm         = null;

      if ( this.props.item["builtin"] ) {
        builtInGroupAlert = (
          <TWBS.Alert bsStyle   = "warning"
                      className = "text-center">
            <b>{"You should only edit a system group if you know exactly what you are doing."}</b>
          </TWBS.Alert>
        );
      }

      editButtons =
        <TWBS.ButtonToolbar>
            <TWBS.Button className = "pull-left"
                         disabled  = { this.props.item["builtin"] }
                         onClick   = { this.deleteGroup }
                         bsStyle   = "danger" >{"Delete Group"}</TWBS.Button>
            <TWBS.Button className = "pull-right"
                         onClick   = { this.props.handleViewChange.bind(null, "view") }
                         bsStyle   = "default" >{"Cancel"}</TWBS.Button>
            <TWBS.Button className = "pull-right"
                         disabled  = { _.isEmpty( this.state.locallyModifiedValues ) ? true : false }
                         onClick   = { this.submitGroupUpdate }
                         bsStyle   = "info" >{"Save Changes"}</TWBS.Button>
        </TWBS.ButtonToolbar>;

      inputForm =
        <form className="form-horizontal">
          <TWBS.Grid fluid>
            <TWBS.Row>
              <TWBS.Col xs = {12}>
                {/*Group id*/}
                <TWBS.Input type             = "text"
                            label            = { "Group ID" }
                            value            = { this.state.mixedValues["id"] ? this.state.mixedValues["id"] : "" }
                            onChange         = { this.editHandleValueChange.bind( null, "id" ) }
                            ref              = { "id" }
                            key              = { "id" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["id"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            disabled         = { !this.isMutable( "id", this.state.dataKeys) } />
                {/* name */}
                <TWBS.Input type             = "text"
                            label            = { "Group Name" }
                            value            = { this.state.mixedValues["name"] ? this.state.mixedValues["name"] : "" }
                            onChange         = { this.editHandleValueChange.bind( null, "name" ) }
                            ref              = { "name" }
                            key              = { "name" }
                            groupClassName   = { _.has(this.state.locallyModifiedValues["name"]) ? "editor-was-modified" : "" }
                            labelClassName   = "col-xs-4"
                            wrapperClassName = "col-xs-8"
                            disabled         = { !this.isMutable( "name", this.state.dataKeys) } />
              </TWBS.Col>
            </TWBS.Row>
          </TWBS.Grid>
        </form>;

      return (
        <TWBS.Grid fluid>
          {/* Save and Cancel Buttons - Top */}
          { editButtons }

          {/* Shows a warning if the group is built in */}
          { builtInGroupAlert }

          {inputForm}

          {/* Save and Cancel Buttons - Bottom */}
          { editButtons }
        </TWBS.Grid>
      );
    }
});


// CONTROLLER-VIEW
const GroupItem = React.createClass({

      propTypes: {
        viewData : React.PropTypes.object.isRequired
      }

    , mixins: [ routerShim, clientStatus ]

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
        return GroupsStore.findGroupByKeyValue( this.props.viewData.format["selectionKey"], this.getDynamicRoute() );
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
          if ( GroupsStore.isLocalTaskPending( this.state.targetGroup["id"] ) ) {
            processingText = "Saving changes to '" + this.state.targetGroup[ this.props.viewData.format["primaryKey" ] ] + "'";
          } else if (GroupsStore.isGroupUpdatePending( this.state.targetGroup[ "id"] ) ) {
            processingText = "Group '" + this.state.targetGroup[ this.props.viewData.format["primaryKey"] ] + "' was updated remotely.";
          }

          // DISPLAY COMPONENT
          var childProps = {
              handleViewChange : this.handleViewChange
            , item             : this.state.targetGroup
            , viewData         : this.props.viewData
          };

          switch( this.state.currentMode ) {
            default:
            case "view":
              DisplayComponent = <GroupView { ...childProps } />;
              break;
            case "edit":
              DisplayComponent = <GroupEdit { ...childProps } />;
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
