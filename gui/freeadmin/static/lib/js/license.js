require([
  "dojo/ready",
  "dojo/request/xhr"
], function(
  ready,
  xhr
) {

    checkLicenseStatus = function () {

      xhr.get('/support/license/status/', {
        preventCache: true,
        handleAs: 'text'
      }).then(function(data) {
        if(data == 'PROMPT') {
          editObject('Update License', '/support/license/update/', []);
        }
      });

    }

    ready(function() {
      checkLicenseStatus();
    });

});
