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
          commonDialog({
            id: "licenseDialog",
            name: 'Update License',
            url: '/support/license/update/',
            nodes: [],
            style: "max-width: 75%;max-height:70%;background-color:white;overflow:auto;"
          });
        }
      });

    }

    ready(function() {
      checkLicenseStatus();
    });

});
