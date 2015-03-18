// System Tools
// =======
//

"use strict";


var React = require("react");

var UpdaterMiddleware = require("../middleware/UpdaterMiddleware");

var Icon = require("../components/Icon")

var ConfDialog = require("../components/common/ConfDialog")

var SystemTools = React.createClass({
  handleupdatenowbutton: function() {
      UpdaterMiddleware.updatenow();
  },

  render: function() {
    var updateText = (<div style = { {margin: "5px"
                                    , cursor: "pointer"} }>
                        <Icon glyph = "bomb"
                              icoSize = "4em"
                        />
                        <br />
                        Update Now!
                      </div>);
    var updateprops = {};
    updateprops.dataText = updateText;
    updateprops.title = "Confirm Update";
    updateprops.bodyText = "Freenas will now Update"
    updateprops.callFunc  = this.handleupdatenowbutton;
    return (
      <main>
        <h2>System Tools View</h2>
        <ConfDialog {...updateprops}/>
      </main>
    );
  }
});

module.exports = SystemTools;