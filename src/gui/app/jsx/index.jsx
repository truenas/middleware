// PRIMARY APP STRUCTURE
// =====================

"use strict";

import React from "react";

var Index = React.createClass({

    propTypes: {

    }

  , componentDidMount: function () {
    }

  , render: function () {

    return (
      <html>
        <head>
          {/* Charset Definition */}
          <meta charSet="utf-8"/>
          <title>FreeNAS 10 GUI</title>

          {/* Robot Instructions */}
          <meta name="robots" content="noindex, nofollow" />

          {/* Favicons */}
          <link rel="icon" type="image/png" href="/favicon-32x32.png" sizes="32x32" />
          <link rel="icon" type="image/png" href="/favicon-16x16.png" sizes="16x16" />

          {/* Primary Styles */}
          <link rel="stylesheet" type="text/css" href="/css/main.css" />

          {/* Libraries */}
          <script type="text/javascript" src="/js/libs.js"></script>

          {/* Main app code */}
          <script defer type="text/javascript" src="/js/app.js"></script>
        </head>
        <body>BODY_RENDER_TARGET</body>
      </html>
    );
  }

});

module.exports = Index;
