// Interface Edit View
// ===================

"use strict";

import _ from "lodash";
import React from "react";
import TWBS from "react-bootstrap";

import viewerCommon from "../../../components/mixins/viewerCommon";
import inputHelpers from "../../../components/mixins/inputHelpers";
import interfaceMixins from "../../../components/mixins/interfaceMixins";

import IM from "../../../middleware/InterfacesMiddleware";

const InterfaceEdit = React.createClass(
  { mixins: [ viewerCommon, inputHelpers, interfaceMixins ]

  , propTypes: { item: React.PropTypes.object.isRequired }

  , getInitialState: function () {
    return {
      locallyModifiedValues : {}
      , mixedValues         : this.props.item
      , remoteState         : this.props.item
      , lastSentValues      : {}
    };
  }

  , submitInterfaceUpdate: function () {
    // Don't let read-only values in.
    var valuesToSend = this.state.locallyModifiedValues;
    if ( !_.isEmpty( valuesToSend ) ) {
      IM.configureInterface(
        this.props.item.name
        , valuesToSend
        , this.submissionRedirect( valuesToSend )
      );

      // Save a record of the last changes sent.
      this.setState({ lastSentValues: valuesToSend });
    }
  }

  , render: function () {
    var editButtons =
      <TWBS.ButtonToolbar>
        <TWBS.Button
          className = 'pull-right'
          onClick   = { this.props.handleViewChange.bind( null, "view" ) }
          bsStyle   = 'default' >
          Cancel
        </TWBS.Button>
        <TWBS.Button
          className = 'pull-right'
          disabled  = { _.isEmpty( this.state.locallyModifiedValues ) }
          onClick   = { this.submitInterfaceUpdate }
          bsStyle   = 'info' >
          Save Changes
        </TWBS.Button>
      </TWBS.ButtonToolbar>;

    var inputForm =
      <form className = "form-horizontal">
        <TWBS.Grid fluid>
          <TWBS.Row>
            <TWBS.Col xs={12}>
              <label>Interface Name</label>
              <div>{ this.state.mixedValues.name }</div>
              <TWBS.Input
                type      = "checkbox"
                label     = "DHCP Enabled"
                checked   = { this.state.mixedValues.dhcp }
                onChange  = { this.editHandleValueChange.bind( null, "dhcp" ) }
                ref       = { "dhcp" }
                key       = { "dhcp" }
                groupClassName =
                  { _.has( this.state.locallyModifiedValues[ "dhcp" ] )
                      ? "editor-was-modified" : "" }
                labelClassName    = "col-xs-3"
                wrapperClassName  = "col-xs-9" />
              <TWBS.Input
                type      = "checkbox"
                label     = "Interface Enabled"
                checked   = { this.state.mixedValues.enabled }
                onChange  =
                  { this.editHandleValueChange.bind( null, "enabled" ) }
                ref       = { "enabled" }
                key       = { "enabled" }
                groupClassName =
                  { _.has( this.state.locallyModifiedValues[ "enabled" ] )
                    ? "editor-was-modified" : "" }
                labelClassName    = "col-xs-3"
                wrapperClassName  = "col-xs-9" />
            </TWBS.Col>
          </TWBS.Row>
        </TWBS.Grid>
      </form>;

    return (
      <TWBS.Grid fluid>
        { editButtons }
        { inputForm }
        { editButtons }
      </TWBS.Grid>
    );
  }

});

export default InterfaceEdit;
