// Update
// =======
//

"use strict";

import React from "react";
import TWBS from "react-bootstrap"

import UpdaterMiddleware from "../../middleware/UpdaterMiddleware";

import Icon from "../../components/Icon";

import ConfDialog from "../../components/common/ConfDialog";

const Update = React.createClass({
  getInitialState: function () {
    return { editSettings: false
           , currentTrain: ""
           , updateCheckAuto: false
           , isUpdateAvailable: false };
  }

  , getInitialConfig: function ( config ) {
    this.setState({ currentTrain: config[ "train" ]
                  , updateCheckAuto: config[ "updateCheckAuto" ] });
  }

  , handleEditModeButton: function ( event ) {
    this.setState({ editSettings: !this.state.editSettings });
  }

  , handleUpdateNowButton: function () {
    UpdaterMiddleware.updatenow();
  }

  , handleUpdateCheckButton: function () {
    UpdaterMiddleware.checkForUpdate();
  }

  , componentDidMount: function () {
    UpdaterMiddleware.getConfig( this.getInitialConfig );
  }

  , render: function () {
    var checkForUpdateText = (  <div style = { {margin: "5px"
                                    , cursor: "pointer"} }>
                                  <a onClick={ this.handleUpdateCheckButton }>
                                  <Icon glyph = "check-circle"
                                    icoSize = "4em" />
                                  <br />
                                    Check for Updates Now
                                  </a>
                               </div> );

    var updateButtonText = (  <div style = { {margin: "5px"
                                    , cursor: "pointer"} }>
                            <Icon glyph = "bomb"
                             icoSize = "4em" />
                            <br />
                            Download and Install
                          </div> );
    var updateButtonProps = {};
    updateButtonProps.dataText = updateButtonText;
    updateButtonProps.title = "Confirm Update";
    updateButtonProps.bodyText = "Freenas will now Update"
    updateButtonProps.callFunc  = this.handleUpdateNowButton;

    var updateServer = "some update server";
    var updatePeriod = "millenia";
    var updateSignature = "some signature";
    var updateTrain = this.state.currentTrain;
    var updateAutoText = "";
    if ( this.state.updateCheckAuto ) {
      updateAutoText = "Updates are automatically fetched every \""
        + updatePeriod + "\"";
    } else {
      updateAutoText = "Updates are set to manual check only";
    }

    let settingsContent;
    if ( this.state.editSettings ) {
      settingsContent = (
        <div>
        <p>{"This is edit mode"}</p>
        <span style={{float: "right"}}>
          <a onClick={this.handleEditModeButton}>Change update settings</a>
        </span>
      </div> );
    } else {
      settingsContent = (
        <div>
          <p> {"You are now on the \"" + updateTrain
           + "\" update train from \"" + updateServer + "\""} <br />
           { updateAutoText } {" and update signature is \""
           + updateSignature + "\""} </p>
          <span style={{float: "right"}}>
            <a onClick={ this.handleEditModeButton }>Change update settings</a>
          </span>
      </div> );
    }

    return (
      <main>
        <h2>Update</h2>
        <TWBS.PanelGroup>
          <TWBS.Panel>
            { settingsContent }
          </TWBS.Panel>
	</TWBS.PanelGroup>
        { checkForUpdateText }
        <ConfDialog {...updateButtonProps}/>
      </main>
    );
  }
});

export default Update;
