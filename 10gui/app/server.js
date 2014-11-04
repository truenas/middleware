// MACH SERVER

"use strict";

require("node-jsx").install();

// Node
var fs   = require("fs");
var path = require("path");

// Server
var mach   = require("mach");
var stack  = mach.stack();
var when   = require("when");

// Routing
var Router = require("react-router");
var routes = require("./routes");

// Content
var baseHTML = fs.readFileSync( __dirname + "/templates/mainlayout.html" ).toString();
var jsBundle = fs.readFileSync( __dirname + "/build/js/app.js" );


// Mach server helpers
function renderApp( path ) {
  var htmlRegex = /¡HTML!/;
  var dataRegex = /¡DATA!/;

  return new when.Promise( function ( resolve, reject ) {
    Router.renderRoutesToString( routes, path, function ( error, abortReason, html, data ) {
      if ( abortReason ) {
        reject({
            redirect : true
          , to       : "/" + abortReason.to + "/" + abortReason.params["id"]
        });
      }

      var output = baseHTML.replace( htmlRegex, html )
                           .replace( dataRegex, JSON.stringify( data ) );

      resolve( output );
    });
  });
}

// Mach server config
// TODO: production mode with different stack options:
// stack.use(mach.gzip);      // Gzip-encode responses
// stack.use(mach.logger);    // Log responses
stack.use( mach.favicon );
stack.use( mach.file, { root: path.join( __dirname, "build" ) } );
stack.run( function ( req, res ) {
  switch ( req.path ) {
    case "/js/app.js":
      return jsBundle;

    default:
      return renderApp( req.path ).then( null, function( redirect ) {
        res.redirect( redirect.to );
      });
  }
});


// Start Mach server
mach.serve( stack, ( process.env.PORT || 3000 ) );
