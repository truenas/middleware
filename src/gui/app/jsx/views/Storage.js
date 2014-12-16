/** @jsx React.DOM */

// Storage
// =======
// View showing files, snapshots, volumes, and disks. Provides utilities to
// manage storage at all levels, including the creation and deletion of ZFS
// pools / volumes, etc.

"use strict";


var React = require("react");

var Storage = React.createClass({
  render: function() {
    return (
      <main>
        <h2>Storage View</h2>
      </main>
    );
  }
});

module.exports = Storage;