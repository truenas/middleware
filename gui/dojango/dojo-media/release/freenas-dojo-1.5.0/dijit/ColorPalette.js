/*
	Copyright (c) 2004-2010, The Dojo Foundation All Rights Reserved.
	Available via Academic Free License >= 2.1 OR the modified BSD license.
	see: http://dojotoolkit.org/license for details
*/


if(!dojo._hasResource["dijit.ColorPalette"]){
dojo._hasResource["dijit.ColorPalette"]=true;
dojo.provide("dijit.ColorPalette");
dojo.require("dijit._Widget");
dojo.require("dijit._Templated");
dojo.require("dojo.colors");
dojo.require("dojo.i18n");
dojo.require("dijit._PaletteMixin");
dojo.requireLocalization("dojo","colors",null,"ROOT,ar,ca,cs,da,de,el,es,fi,fr,he,hu,it,ja,ko,nb,nl,pl,pt,pt-pt,ro,ru,sk,sl,sv,th,tr,zh,zh-tw");
dojo.declare("dijit.ColorPalette",[dijit._Widget,dijit._Templated,dijit._PaletteMixin],{palette:"7x10",_palettes:{"7x10":[["white","seashell","cornsilk","lemonchiffon","lightyellow","palegreen","paleturquoise","lightcyan","lavender","plum"],["lightgray","pink","bisque","moccasin","khaki","lightgreen","lightseagreen","lightskyblue","cornflowerblue","violet"],["silver","lightcoral","sandybrown","orange","palegoldenrod","chartreuse","mediumturquoise","skyblue","mediumslateblue","orchid"],["gray","red","orangered","darkorange","yellow","limegreen","darkseagreen","royalblue","slateblue","mediumorchid"],["dimgray","crimson","chocolate","coral","gold","forestgreen","seagreen","blue","blueviolet","darkorchid"],["darkslategray","firebrick","saddlebrown","sienna","olive","green","darkcyan","mediumblue","darkslateblue","darkmagenta"],["black","darkred","maroon","brown","darkolivegreen","darkgreen","midnightblue","navy","indigo","purple"]],"3x4":[["white","lime","green","blue"],["silver","yellow","fuchsia","navy"],["gray","red","purple","black"]]},_imagePaths:{"7x10":dojo.moduleUrl("dijit.themes","a11y/colors7x10.png"),"3x4":dojo.moduleUrl("dijit.themes","a11y/colors3x4.png"),"7x10-rtl":dojo.moduleUrl("dijit.themes","a11y/colors7x10-rtl.png"),"3x4-rtl":dojo.moduleUrl("dijit.themes","a11y/colors3x4-rtl.png")},templateString:dojo.cache("dijit","templates/ColorPalette.html","<div class=\"dijitInline dijitColorPalette\">\n\t<img class=\"dijitColorPaletteUnder\" dojoAttachPoint=\"imageNode\" waiRole=\"presentation\" alt=\"\"/>\n\t<table class=\"dijitPaletteTable\" cellSpacing=\"0\" cellPadding=\"0\">\n\t\t<tbody dojoAttachPoint=\"gridNode\"></tbody>\n\t</table>\n</div>\n"),baseClass:"dijitColorPalette",dyeClass:"dijit._Color",buildRendering:function(){
this.inherited(arguments);
this.imageNode.setAttribute("src",this._imagePaths[this.palette+(this.isLeftToRight()?"":"-rtl")].toString());
var _1=dojo.i18n.getLocalization("dojo","colors",this.lang);
this._preparePalette(this._palettes[this.palette],_1);
}});
dojo.declare("dijit._Color",dojo.Color,{constructor:function(_2){
this._alias=_2;
this.setColor(dojo.Color.named[_2]);
},getValue:function(){
return this.toHex();
},fillCell:function(_3,_4){
dojo.create("img",{src:_4,"class":"dijitPaletteImg",alt:this._alias},_3);
}});
}
