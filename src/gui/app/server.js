// MACH SERVER

"use strict";

var fs   = require("fs");
var path = require("path");
var mach = require("mach");
var when = require("when");

var React  = require("react");
var Router = require("react-router");

var routes = require("./ssrjs/routes");

// Content
var baseHTML = fs.readFileSync( __dirname + "/templates/mainlayout.html" ).toString();
var jsBundle = fs.readFileSync( __dirname + "/build/js/app.js" );

var app = mach.stack();


// Mach server helpers
function renderApp( path ) {
  var bodyRegex = /¡HTML!/;
  var dataRegex = /¡DATA!/;

  return new when.Promise( function ( resolve, reject ) {
    Router.run( routes, path, function ( Handler ) {
      var innerHTML = React.renderToString( React.createElement( Handler ) );
      var output    = baseHTML.replace( bodyRegex, innerHTML )
                              .replace( dataRegex, null );

      if ( baseHTML && innerHTML && output ) {
        resolve( output );
      } else {
        reject( "Handler for " + path + " did not return any HTML when rendered to string" );
      }
    });
  });
}

// Mach server config
// TODO: production mode with different stack options:
// app.use(mach.gzip);      // Gzip-encode responses
// app.use(mach.logger);    // Log responses
app.use( mach.favicon );
app.use( mach.file, { root: path.join( __dirname, "build" ) } );
app.run( function ( req, res ) {

  switch ( req.path ) {
    case "/js/app.js":
      return jsBundle;

    default:
      return renderApp( req.path );
  }

});


// Start Mach server
mach.serve( app, ( process.env.PORT || 3000 ) );
