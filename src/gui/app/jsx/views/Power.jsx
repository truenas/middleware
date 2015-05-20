// Power
// =======
//

"use strict";

import React from "react";

import PowerMiddleware from "../middleware/PowerMiddleware";

import Icon from "../components/Icon";

import ConfDialog from "../components/common/ConfDialog";

const Power = React.createClass({
  handlerebootbutton: function () {
      PowerMiddleware.reboot();
  },

  handleshutdownbutton: function () {
      PowerMiddleware.shutdown();
  },

  render: function () {
    var rebootprops        = {};
    rebootprops.dataText   = (<div style = { {margin: "5px"
                                     , cursor: "pointer"} }>
                                <Icon glyph = "refresh"
                                     icoSize = "4em" />
                                <br />
                                Reboot
                              </div>);
    rebootprops.title      = "Confirm Reboot";
    rebootprops.bodyText   = "Are you sure you wish to reboot?";
    rebootprops.callFunc   = this.handlerebootbutton;
    var shutdownprops      = {};
    shutdownprops.dataText = (<div style = { {margin: "5px"
                                    , cursor: "pointer"} }>
                                <Icon glyph = "power-off"
                                      icoSize = "4em" />
                                <br />
                                Shutdown
                              </div>);
    shutdownprops.title    = "Confirm Shutdown";
    shutdownprops.bodyText = "Are you sure you wish to Shutdown?";
    shutdownprops.callFunc = this.handleshutdownbutton;
    return (
      <main>
        <h2>Power View</h2>
        <ConfDialog {...rebootprops}/>
        <ConfDialog {...shutdownprops}/>
      </main>
    );
  }
});

export default Power;
