// SSH HELPERS

"use strict";

var chalk = require( "chalk" );

var SshHelpers = function ( grunt ) {
  // Test that a response was issued, and that it contains the provided string
  this.logSshMsg = function ( string, chalkClass ) {
    grunt.log.writeln( "Status: " +
                         chalkClass
                       ? chalk[ chalkClass ]( string )
                       : string
    );
  };

  // Simple truth test to determine if a given stdout response contains the
  // specified word or phrase
  this.responseContains = function ( response, testString ) {
    if ( typeof response === "string" &&
         response.indexOf( testString ) !== -1 ) {
      return true;
    } else {
      return false;
    }
  };

  // Output the server's address, neatly formatted
  this.printServerAddress = function ( state ) {
    var whitespace = "  ";
    var yAxis      = "//";
    var xAxis;

    var hostAddress = whitespace +
                      grunt.config( [ "freeNASConfig" ] )["remoteHost"] +
                      whitespace;
    var failMessage = whitespace + "Server did not start!" + whitespace;


    var repChar = function ( character, times ) {
      return new Array( times + 1 ).join( character );
    };

    if ( state === "starting" ) {
      xAxis = repChar( "/", hostAddress.length + ( yAxis.length * 2 ) );

      grunt.log.writeln( "\n\nThe FreeNAS GUI webserver service is being " +
                         "restarted\nIt should soon be available at this " +
                         "address:\n" );

      grunt.log.writeln( chalk.bgGreen( xAxis ) );
      grunt.log.writeln( chalk.bgGreen( yAxis ) + hostAddress +
                         chalk.bgGreen( yAxis ) );
      grunt.log.writeln( chalk.bgGreen( xAxis ) );
    } else {
      xAxis = repChar( "/", failMessage.length + ( yAxis.length * 2 ) );

      grunt.log.writeln( chalk.bgRed( xAxis ) );
      grunt.log.writeln( chalk.bgRed( yAxis ) + failMessage +
                         chalk.bgRed( yAxis ) );
      grunt.log.writeln( chalk.bgRed( xAxis ) );

      grunt.fatal( "An error occurred when trying to `start` or `restart` " +
                   "`/usr/sbin/service gui`" );
    }
  };

};

module.exports = SshHelpers;
