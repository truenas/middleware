// Flux Dispatcher for Viewer component

"use strict";

var Dispatcher     = require("flux").Dispatcher;
var copyProperties = require('react/lib/copyProperties');

var ViewerDispatcher = copyProperties(new Dispatcher() {

});

module.exports = ViewerDispatcher;