/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dojango.dojango"]){
dojo._hasResource["dojango.dojango"]=true;
dojo.provide("dojango.dojango");
dojango.registerModulePath=function(_1,_2,_3){
if(dojo.config.useXDomain){
dojo.registerModulePath(_1,_2.substring(1));
}else{
if(dojangoConfig.isLocalBuild){
dojo.registerModulePath(_1,"../"+_1);
}else{
dojo.registerModulePath(_1,_3);
}
}
};
dojo.require("dojango._base");
}
