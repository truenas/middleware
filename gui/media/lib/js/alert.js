/*-
 * Copyright (c) 2011 iXsystems, Inc.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 *
 */

dojo.require('dojox.timing');

var _alert_status = 'OK';

function loadalert() {

    var url = '/admin/alert/status/?' + new Date().getTime();
    dojo.xhrGet({
        url: url,
        handleAs: "text",
        load: function(data) {

            var alertdiv = dojo.byId("alert_status");
            if(data == _alert_status)
                return true;
            _alert_status = data;
            if(data == 'OK') {
                dojo.removeClass(alertdiv, ["alert_crit", "alert_warn"]);
                dojo.addClass(alertdiv, "alert_ok");
            } else if(data == 'WARN') {
                dojo.removeClass(alertdiv, ["alert_crit", "alert_ok"]);
                dojo.addClass(alertdiv, "alert_warn");
            } else if(data == 'CRIT') {
                dojo.removeClass(alertdiv, ["alert_warn", "alert_ok"]);
                dojo.addClass(alertdiv, "alert_crit");
            }

        },
    });
}

alert_open = function() {
    var alertdlg = new dijit.Dialog({
        title: "Alert System",
        style: "width: 400px",
        id: "alert_dialog",
        href: "/admin/alert/",
        onHide: function() {
            setTimeout(dojo.hitch(this, 'destroyRecursive'), dijit.defaultDuration);
        },
    });
    alertdlg.show();
}

dojo.addOnLoad(function(){

    var talert = new dojox.timing.Timer(1000*60*5);

    talert.onTick = function() {
        loadalert();
    }
    talert.onStart = function() {
        loadalert();
    }
    talert.start();

});
