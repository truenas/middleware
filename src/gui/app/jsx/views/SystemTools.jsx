// System Tools
// =======
//

"use strict";


var React = require("react");

var UpdaterMiddleware = require("../middleware/UpdaterMiddleware");

var Icon = require("../components/Icon")

var SystemTools = React.createClass({
  handleupdatenowbutton: function() {
      UpdaterMiddleware.updatenow();
  },
  render: function() {
    return (
      <main>
        <h2>System Tools View</h2>
        <div style= { {margin: "5px"} }>
          <Icon glyph = "bomb"
                icoSize = "4em"
                onClick  = { this.handleupdatenowbutton }
          />
          <br />
          Update Now!
        </div>
      </main>
    );
  }
});

module.exports = SystemTools;