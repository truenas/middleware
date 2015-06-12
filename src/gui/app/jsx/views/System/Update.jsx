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
           , updateAutoCheck: false };
  }

  , getInitialConfig: function ( config ) {
    this.setState({ currentTrain: config[ "train" ]
                  , updateAutoCheck: config[ "updateCheckAuto" ] });
  }

  , handleEditModeButton: function ( event ) {
    this.setState({ editSettings: !this.state.editSettings });
  }

  , handleupdatenowbutton: function () {
    UpdaterMiddleware.updatenow();
  }

  , componentDidMount: function () {
      UpdaterMiddleware.getConfig( this.getInitialConfig );
    }

  , render: function () {
    var updateText = (  <div style = { {margin: "5px"
                                    , cursor: "pointer"} }>
                            <Icon glyph = "bomb"
                             icoSize = "4em" />
                            <br />
                            Update
                          </div> );
    var updateprops = {};
    updateprops.dataText = updateText;
    updateprops.title = "Confirm Update";
    updateprops.bodyText = "Freenas will now Update"
    updateprops.callFunc  = this.handleupdatenowbutton;

    var updateServer = "some update server";
    var updatePeriod = "millenia";
    var updateSignature = "some signature";
    var updateTrain = this.state.currentTrain;
    var updateAutoText = "";
    if ( this.state.updateAutoCheck ) {
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
            <a onClick={this.handleEditModeButton}>Change update settings</a>
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
        <ConfDialog {...updateprops}/>
      </main>
    );
  }
});

export default Update;
