// Generic set of functions to use for cookie manipulation
// add, delete and that sort of thing

"use strict";

var myCookies = {
  obtain: function (cookieName) {
    if (typeof cookieName === 'undefined') { return null; }
    return decodeURIComponent(document.cookie.replace(new RegExp("(?:(?:^|.*;)\\s*" + encodeURIComponent(cookieName).replace(/[\-\.\+\*]/g, "\\$&") + "\\s*\\=\\s*([^;]*).*$)|^.*$"), "$1")) || null;
  },
  add: function (cookieName, cookieContent, cookieMaxAge, cookiePath, cookieDomain, cookieSecure) {
    // cookieMaxAge is to be specified in seconds
    if (typeof cookieName === 'undefined'|| /^(?:max\-age|path|domain|secure)$/i.test(cookieName)) { return false; }
    document.cookie = encodeURIComponent(cookieName) + "=" + encodeURIComponent(cookieContent) + (cookieMaxAge ? "; max-age=" + cookieMaxAge : "") + (cookieDomain ? "; domain=" + cookieDomain : "") + (cookiePath ? "; path=" + cookiePath : "") + (cookieSecure ? "; secure" : "");
    return true;
  },
  delete: function (cookieName, cookiePath, cookieDomain) {
    if (!this.obtain(cookieName)) { return false; }
    document.cookie = encodeURIComponent(cookieName) + "=; max-age=0" + (cookieDomain ? "; domain=" + cookieDomain : "") + (cookiePath ? "; path=" + cookiePath : "");
    return true;
  }
};

module.exports = myCookies;
