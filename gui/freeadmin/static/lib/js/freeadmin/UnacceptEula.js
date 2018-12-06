var hadCtrlB = false;
document.addEventListener("keypress", function(e) {
  if (e.ctrlKey && e.key == "b")
  {
    hadCtrlB = true;
  }
  else if (hadCtrlB && e.key == "e")
  {
    document.getElementById("unaccept_eula_form").submit();
  }
  else
  {
    hadCtrlB = false;
  }
});


define([
  "dojo/_base/declare"
], function(
  declare
) {
  return declare("freeadmin.UnacceptEula", [], {});
});
