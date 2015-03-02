// Power
// =======
//

"use strict";


var React = require("react");

var PowerMiddleware = require("../middleware/PowerMiddleware");

var Icon = require("../components/Icon")

var Power = React.createClass({
  handlerebootbutton: function() {
      PowerMiddleware.reboot();
  },
  handleshutdownbutton: function() {
      PowerMiddleware.shutdown();
  },
  render: function() {
    return (
      <main>
        <h2>Power View</h2>
        <div style = { {margin: "5px"} }>
          <Icon glyph = "refresh"
                icoSize = "4em"
                onClick  = { this.handlerebootbutton }
          />
          <br />
          Reboot
        </div>
        <div style = { {margin: "5px"} }>
          <Icon glyph = "power-off"
                icoSize = "4em"
                onClick  = { this.handleshutdownbutton }
          />
          <br />
          Shutdown
        </div>
      </main>
    );
  }
});

module.exports = Power;
