/** @jsx React.DOM */

// Information Bar
// ===============
// Part of the main webapp's window chrome. Positioned on the right side of the
// page, this bar shows user-customizable content including graphs, logged in
// users, and other widgets.

"use strict";

var React = require("react");


var InformationBar = React.createClass({
    render: function () {
      return (
        <aside className="app-sidebar information-bar">

        </aside>
      );
    }
});

module.exports = InformationBar;
