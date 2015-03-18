// Power
// =======
//

"use strict";


var React = require("react");

var PowerMiddleware = require("../middleware/PowerMiddleware");

var Icon = require("../components/Icon")

var ConfDialog = require("../components/common/ConfDialog")

var Power = React.createClass({
  handlerebootbutton: function() {
      PowerMiddleware.reboot();
  },

  handleshutdownbutton: function() {
      PowerMiddleware.shutdown();
  },

  render: function() {
    var rebootText = (<div style = { {margin: "5px"
                                    , cursor: "pointer"} }>
                        <Icon glyph = "refresh"
                              icoSize = "4em"
                        />
                        <br />
                        Reboot
                      </div>);
    var rebootprops = {};
    rebootprops.dataText = rebootText;
    rebootprops.title = "Confirm Reboot";
    rebootprops.bodyText = "Are you sure you wish to reboot?"
    rebootprops.callFunc  = this.handlerebootbutton;
    var shutdownText = (<div style = { {margin: "5px"
                                    , cursor: "pointer"} }>
                        <Icon glyph = "power-off"
                              icoSize = "4em"
                        />
                        <br />
                        Shutdown
                      </div>);
    var shutdownprops = {};
    shutdownprops.dataText = shutdownText;
    shutdownprops.title = "Confirm Shutdown";
    shutdownprops.bodyText = "Are you sure you wish to Shutdown?"
    shutdownprops.callFunc  = this.handleshutdownbutton;
    return (
      <main>
        <h2>Power View</h2>
        <ConfDialog {...rebootprops}/>
        <ConfDialog {...shutdownprops}/>
      </main>
    );
  }
});

module.exports = Power;
