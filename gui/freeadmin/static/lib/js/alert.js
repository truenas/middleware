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

require([
    "dojo/_base/lang",
    "dojo/dom",
    "dojo/dom-class",
    "dojo/ready",
    "dojo/request/xhr",
    "dijit/_base/manager",
    "dijit/Dialog",
    "dojox/timing"
    ], function(
    lang,
    dom,
    domClass,
    ready,
    xhr,
    manager,
    Dialog,
    timing
    ) {

    var _alert_status = '';

    loadalert = function() {

        var url = '/admin/alert/status/?' + new Date().getTime();
        xhr.get(url, {
            handleAs: "text"
            }).then(function(data) {

                var alertdiv = dom.byId("alert_status");
                var alerttext = dom.byId("menuBar_AlertText");
                if(data == _alert_status)
                    return true;
                _alert_status = data;
                if(data == 'OK') {
                    domClass.remove(alertdiv, ["alert_crit", "alert_warn"]);
                    domClass.add(alertdiv, "alert_ok");
                    alerttext.innerHTML = gettext('OK');
                } else if(data == 'WARN') {
                    domClass.remove(alertdiv, ["alert_crit", "alert_ok"]);
                    domClass.add(alertdiv, "alert_warn");
                    alerttext.innerHTML = gettext('Warning');
                } else if(data == 'CRIT') {
                    domClass.remove(alertdiv, ["alert_warn", "alert_ok"]);
                    domClass.add(alertdiv, "alert_crit");
                    alerttext.innerHTML = gettext('Critical');
                }

            });
    }

    alert_open = function() {
        var alertdlg = new Dialog({
            title: gettext("Alert System"),
            style: "width: 600px",
            id: "alert_dialog",
            href: "/admin/alert/",
            onHide: function() {
                setTimeout(lang.hitch(this, 'destroyRecursive'), manager.defaultDuration);
            }
        });
        alertdlg.show();
        loadalert();
    }

    ready(function(){

        var talert = new timing.Timer(1000*60*5);

        talert.onTick = function() {
            loadalert();
        }
        talert.onStart = function() {
            loadalert();
        }
        talert.start();

    });

});
