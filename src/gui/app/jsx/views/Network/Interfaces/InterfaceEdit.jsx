// Interface Edit View
// ===================

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import viewerCommon from "../../../components/mixins/viewerCommon";
import inputHelpers from "../../../components/mixins/inputHelpers";

import IM from "../../../middleware/InterfacesMiddleware";

const InterfaceEdit = React.createClass({

  mixins: [ viewerCommon
          , inputHelpers
          ]

  , contextTypes: { router: React.PropTypes.func }

  , propTypes: { item: React.PropTypes.object.isRequired
               , viewData: React.PropTypes.object.isRequired
               }

  , getInitialState: function () {
    let remoteState = this.setRemoteState( this.props );

    return { locallyModifiedValues : {}
           , remotelyModifiedValues: {}
           , remoteState: remoteState
           , mixedValues: this.props.item
           , lastSentValues: {}
           }
  }

  // Initially copied from UserEdit.
  // TODO: Eliminate this duplication if at all possible.
  , componentWillReceiveProps: function ( nextProps ) {
    let newRemoteModified  = {};
    let newLocallyModified = {};
    let dataKeys = nextProps.viewData[ "format" ][ "dataKeys" ];

    // remotelyModifiedValues represents everything that's changed remotely
    // since the view was opened. This is the difference between the newly
    // arriving props and the initial ones. Read-only and unknown values are
    // ignored.
    // TODO: Use this to show alerts for remote changes on sections the local
    // administrator is working on.
    let mismatchedRemoteFields =
      _.pick( nextProps.item
        , function checkMatch ( value, key ) {
          return _.isEqual( this.state.remoteState[ key ]
                          , value );
        }
        , this
        );

    newRemoteModified = this.removeReadOnlyFields( mismatchedRemoteFields
                                                 , dataKeys
                                                 );

    // remoteState records the item as it was when the view was first
    // opened. This is used to mark changes that have occurred remotely since
    // the user began editing.
    // It is important to know if the incoming change resulted from a call
    // made by the local administrator. When this happens, we reset the
    // remoteState to get rid of remote edit markers, as the local version
    // has thus become authoritative.
    // We check this by comparing the incoming changes (newRemoteModified) to
    // the last request sent (this.state.lastSentValues). If this check
    // succeeds, we reset newLocallyModified and newRemoteModified, as there are
    // no longer any remote or local changes to record.
    // TODO: Do this in a deterministic way, instead of relying on comparing
    // values.
    if ( _.isEqual( this.state.lastSentValues, newRemoteModified ) ) {
      newRemoteModified  = {};
      newLocallyModified = {};
      this.setState( { remoteState: this.setRemoteState( nextProps )
                     , locallyModifiedValues: newLocallyModified
                     }
                   );
    }

    this.setState( { remotelyModifiedValues: newRemoteModified } );
  }

  , submitInterfaceConfigureTask: function () {
    // Don't let read-only values in.
    let locallyModifiedValues = this.state.locallyModifiedValues;
    let mixedValues = this.state.mixedValues;

    let dataKeys = this.props.viewData[ "format" ][ "dataKeys" ];
    let valuesToSend = this.removeReadOnlyFields( locallyModifiedValues
                                                , dataKeys
                                                );
    console.log( "valuesToSend", valuesToSend );
    if ( !_.isEmpty( valuesToSend ) ) {
      IM.configureInterface( this.props.item[ "name" ]
                           , valuesToSend
                           , this.submissionRedirect( valuesToSend )
                           );
      this.setState({ lastSentValues: valuesToSend });
    } else {
      console.warn( "Attempted to sent an Interface Configure task"
                  + " with no valid fields"
                  );
    }
  }

  , render: function () {
    let locallyModifiedValues = this.state.locallyModifiedValues;
    let mixedValues = this.state.mixedValues;

    let nameValue = mixedValues[ "name" ]
                  ? mixedValues[ "name" ]
                  : "";

    let mtuValue = mixedValues[ "mtu" ]
                 ? mixedValues[ "mtu" ].toString()
                 : "";

    let editButtons =
      <TWBS.ButtonToolbar>
        {/*<TWBS.Button className = "pull-left"
                        disabled = { this.props.item["builtin"] }
                        onClick = { this.deleteGroup }
                        bsStyle = "danger" >
             {"Delete Interface"}
           </TWBS.Button>*/}
          <TWBS.Button className = "pull-right"
                       onClick = { this.props.handleViewChange.bind( null
                                                                   , "view"
                                                                   )
                                 }
                       bsStyle = "default" >
            {"Cancel"}
          </TWBS.Button>
          <TWBS.Button className = "pull-right"
                       disabled = { _.isEmpty( locallyModifiedValues )
                                             ? true
                                             : false }
                       onClick = { this.submitInterfaceConfigureTask }
                       bsStyle = "info" >{"Save Changes"}</TWBS.Button>
      </TWBS.ButtonToolbar>;

    let inputForm = <form className = "form-horizontal">
      <TWBS.Grid fluid>
        <TWBS.Row>
          <TWBS.Col xs={12}>
            {/* Interface Name */}
            <TWBS.Input
              type = "text"
              label = "Interface Name"
              value = { nameValue }
              onChange = { this.editHandleValueChange.bind( null, "name" ) }
              ref = { "name" }
              key = { "name" }
              groupClassName = { _.has( locallyModifiedValues[ "name" ]
                                      ? "editorWasModified"
                                      : ""
                                      )
                               }
              labelClassName = "col-xs-3"
              wrapperClassName = "col-xs-9"
            />
          {/* DHCP */}
          <TWBS.Input
            type = "checkbox"
            label = "DHCP Enabled"
            checked = { mixedValues[ "dhcp" ] }
            onChange = { this.editHandleValueChange.bind( null, "dhcp" ) }
            ref = { "dhcp" }
            key = { "dhcp" }
            groupClassName = { _.has( locallyModifiedValues[ "dhcp" ]
                                    ? "editorWasModified"
                                    : ""
                                    )
                             }
            labelClassName = "col-xs-3"
            wrapperClassName = "col-xs-9"
          />
          {/* enabled */}
          <TWBS.Input
            type = "checkbox"
            label = "Interface Enabled"
            checked = { mixedValues[ "enabled" ] }
            onChange = { this.editHandleValueChange.bind( null, "enabled" ) }
            ref = { "enabled" }
            key = { "enabled" }
            groupClassName = { _.has( locallyModifiedValues[ "enabled" ]
                                    ? "editorWasModified"
                                    : ""
                                    )
                             }
            labelClassName = "col-xs-3"
            wrapperClassName = "col-xs-9"
          />
          {/* MTU - Hidden until safe validation can be performed.*/}
         {/*<TWBS.Input
              type = "text"
              label = "MTU"
              value = { mtuValue }
              onChange = { this.editHandleValueChange.bind( null, "mtu" ) }
              ref = { "mtu" }
              key = { "mtu" }
              groupClassName = { _.has( locallyModifiedValues[ "mtu" ]
                                      ? "editorWasModified"
                                      : ""
                                      )
                               }
              labelClassName = "col-xs-3"
              wrapperClassName = "col-xs-9"
            />*/}
          </TWBS.Col>
        </TWBS.Row>
      </TWBS.Grid>
    </form>

    return (
      <div className = "container-fluid" >
        { editButtons }
        { inputForm }
      </div>
    )

  }

});

export default InterfaceEdit;
