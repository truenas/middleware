// Update
// =======
//

"use strict";

import React from "react";
import TWBS from "react-bootstrap"
import Icon from "../../components/Icon";
import ConfDialog from "../../components/common/ConfDialog";

// Middlewares
import UpdaterMiddleware from "../../middleware/UpdaterMiddleware";
import TasksMiddleware from "../../middleware/TasksMiddleware";

// Stores
import TasksStore from "../../stores/TasksStore";
import UpdaterStore from "../../stores/UpdaterStore";

const Update = React.createClass(
  { displayName: "Update View - System:Update Tab"

  , getInitialState: function () {
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
    let checkForUpdateText = (  <div style = { {margin: "5px"
                                    , cursor: "pointer"} }>
                                  <a onClick={ this.handleUpdateCheckButton }>
                                  <Icon glyph = "check-circle"
                                    icoSize = "4em" />
                                  <br />
                                    Check for Updates Now
                                  </a>
                               </div> );

    let updateButtonText = (  <div style = { {margin: "5px"
                                    , cursor: "pointer"} }>
                            <Icon glyph = "bomb"
                             icoSize = "4em" />
                            <br />
                            Download and Install
                          </div> );
    let updateButtonProps = {};
    updateButtonProps.dataText = updateButtonText;
    updateButtonProps.title = "Confirm Update";
    updateButtonProps.bodyText = "Freenas will now Update";
    updateButtonProps.callFunc = this.handleUpdateNowButton;

    let updateServer = "some update server";
    let updatePeriod = "millenia";
    let updateSignature = "some signature";
    let updateTrain = this.state.currentTrain;
    let updateAutoText = "";
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
