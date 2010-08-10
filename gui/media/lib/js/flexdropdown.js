/* Flex Level Drop Down Menu v1.1
* Created: Jan 5th, 2010 by DynamicDrive.com. This notice must stay intact for usage 
* Author: Dynamic Drive at http://www.dynamicdrive.com/
* Visit http://www.dynamicdrive.com/ for full source code
*/

//Version 1.1 (Feb 19th, 2010): Each flex menu (UL) can now be associated with a link dynamically, and/or defined using JavaScript instead of as markup.

//Usage: $(elementselector).addflexmenu('menuid', options)
//ie:
//jQuery(document).ready(function($){
	//$('a.mylinks').addflexmenu('flexmenu1') //apply flex menu with ID "flexmenu1" to links with class="mylinks"
//})

jQuery.noConflict()

var flexdropdownmenu={
	arrowpath: '/freenas/media/images/arrow.gif', //full URL or path to arrow image
	animspeed: 200, //reveal animation speed (in milliseconds)
	showhidedelay: [150, 150], //delay before menu appears and disappears when mouse rolls over it, in milliseconds

	//***** NO NEED TO EDIT BEYOND HERE
	startzindex:1000,
	builtflexmenuids: [], //ids of flex menus already built (to prevent repeated building of same flex menu)

	positionul:function($, $ul, e, $anchor){
		var istoplevel=$ul.hasClass('jqflexmenu') //Bool indicating whether $ul is top level flex menu DIV
		var docrightedge=$(document).scrollLeft()+$(window).width()-40 //40 is to account for shadows in FF
		var docbottomedge=$(document).scrollTop()+$(window).height()-40
		if (istoplevel){ //if main flex menu DIV
			var offsets=$anchor.offset()
			var anchorsetting=$anchor.data('setting')
			var x=offsets.left+anchorsetting.useroffsets[0]+(anchorsetting.dir=="h"? $anchor.outerWidth() : 0) //x pos of main flex menu UL
			var y=offsets.top+anchorsetting.useroffsets[1]+(anchorsetting.dir=="h"? 0 : $anchor.outerHeight())
			x=(x+$ul.data('dimensions').w > docrightedge)? x-(anchorsetting.useroffsets[0]*2)-$ul.data('dimensions').w+$anchor.outerWidth()+(anchorsetting.dir=="h"? -($anchor.outerWidth()*2) : 0) : x //if not enough horizontal room to the ridge of the cursor
			y=(y+$ul.data('dimensions').h > docbottomedge)? y-(anchorsetting.useroffsets[1]*2)-$ul.data('dimensions').h-$anchor.outerHeight()+(anchorsetting.dir=="h"? ($anchor.outerHeight()*2) : 0) : y
		}
		else{ //if sub level flex menu UL
			var $parentli=$ul.data('$parentliref')
			var parentlioffset=$parentli.offset()
			var x=$ul.data('dimensions').parentliw //x pos of sub UL
			var y=0
			x=(parentlioffset.left+x+$ul.data('dimensions').w > docrightedge)? x-$ul.data('dimensions').parentliw-$ul.data('dimensions').w : x //if not enough horizontal room to the ridge parent LI
			y=(parentlioffset.top+$ul.data('dimensions').h > docbottomedge)? y-$ul.data('dimensions').h+$ul.data('dimensions').parentlih : y
		}
		$ul.css({left:x, top:y})
	},
	
	showbox:function($, $flexmenu, e){
		clearTimeout($flexmenu.data('timers').hidetimer)
		$flexmenu.data('timers').showtimer=setTimeout(function(){$flexmenu.show(flexdropdownmenu.animspeed)}, this.showhidedelay[0])
	},

	hidebox:function($, $flexmenu){
		clearTimeout($flexmenu.data('timers').showtimer)
		$flexmenu.data('timers').hidetimer=setTimeout(function(){$flexmenu.hide(100)}, this.showhidedelay[1]) //hide flex menu plus all of its sub ULs
	},


	buildflexmenu:function($, $menu, $target){
		$menu.css({display:'block', visibility:'hidden', zIndex:this.startzindex}).addClass('jqflexmenu').appendTo(document.body)
		$menu.bind('mouseenter', function(){
			clearTimeout($menu.data('timers').hidetimer)
		})		
		$menu.bind('mouseleave', function(){ //hide menu when mouse moves out of it
			flexdropdownmenu.hidebox($, $menu)
		})
		$menu.data('dimensions', {w:$menu.outerWidth(), h:$menu.outerHeight()}) //remember main menu's dimensions
		$menu.data('timers', {})
		var $lis=$menu.find("ul").parent() //find all LIs within menu with a sub UL
		$lis.each(function(i){
			var $li=$(this).css({zIndex: 1000+i})
			var $subul=$li.find('ul:eq(0)').css({display:'block'}) //set sub UL to "block" so we can get dimensions
			$subul.data('dimensions', {w:$subul.outerWidth(), h:$subul.outerHeight(), parentliw:this.offsetWidth, parentlih:this.offsetHeight})
			$subul.data('$parentliref', $li) //cache parent LI of each sub UL
			$subul.data('timers', {})
			$li.data('$subulref', $subul) //cache sub UL of each parent LI
			$li.children("a:eq(0)").append( //add arrow images
				'<img src="'+flexdropdownmenu.arrowpath+'" class="rightarrowclass" style="border:0;" />'
			)
			$li.bind('mouseenter', function(e){ //show sub UL when mouse moves over parent LI
				var $targetul=$(this).css('zIndex', ++flexdropdownmenu.startzindex).addClass("selected").data('$subulref')
				if ($targetul.queue().length<=1){ //if 1 or less queued animations
					clearTimeout($targetul.data('timers').hidetimer)
					$targetul.data('timers').showtimer=setTimeout(function(){
						flexdropdownmenu.positionul($, $targetul, e)
						$targetul.show(flexdropdownmenu.animspeed)
					}, flexdropdownmenu.showhidedelay[0])
				}
			})
			$li.bind('mouseleave', function(e){ //hide sub UL when mouse moves out of parent LI
				var $targetul=$(this).data('$subulref')
				clearTimeout($targetul.data('timers').showtimer)
				$targetul.data('timers').hidetimer=setTimeout(function(){$targetul.hide(100).data('$parentliref').removeClass('selected')}, flexdropdownmenu.showhidedelay[1])
			})
		})
		$menu.find('ul').andSelf().css({display:'none', visibility:'visible'}) //collapse all ULs again
		this.builtflexmenuids.push($menu.get(0).id) //remember id of flex menu that was just built
	},

	

	init:function($, $target, $flexmenu){
		if (this.builtflexmenuids.length==0){ //only bind click event to document once
			$(document).bind("click", function(e){
				if (e.button==0){ //hide all flex menus (and their sub ULs) when left mouse button is clicked
					$('.jqflexmenu').find('ul').andSelf().hide()
				}
			})
		}
		if (jQuery.inArray($flexmenu.get(0).id, this.builtflexmenuids)==-1) //if this flex menu hasn't been built yet
			this.buildflexmenu($, $flexmenu, $target)
		if ($target.parents().filter('ul.jqflexmenu').length>0) //if $target matches an element within the flex menu markup, don't bind onflexmenu to that element
			return
		var useroffsets=$target.attr('data-offsets')? $target.attr('data-offsets').split(',') : [0,0] //get additional user offsets of menu
		useroffsets=[parseInt(useroffsets[0]), parseInt(useroffsets[1])]
		$target.data('setting', {dir: $target.attr('data-dir'), useroffsets: useroffsets}) //store direction (drop right or down) of menu plus user offsets
		$target.bind("mouseenter", function(e){
			$flexmenu.css('zIndex', ++flexdropdownmenu.startzindex)
			flexdropdownmenu.positionul($, $flexmenu, e, $target)
			flexdropdownmenu.showbox($, $flexmenu, e)
		})
		$target.bind("mouseleave", function(e){
			flexdropdownmenu.hidebox($, $flexmenu)
		})
	}
}

jQuery.fn.addflexmenu=function(flexmenuid, options){
	var $=jQuery
	return this.each(function(){ //return jQuery obj
		var $target=$(this)
		if (typeof options=="object"){ //if options parameter defined
			if (options.dir)
				$target.attr('data-dir', options.dir) //set/overwrite data-dir attr with defined value
			if (options.offsets)
				$target.attr('data-offsets', options.offsets) //set/overwrite data-offsets attr with defined value
		}
		if ($('#'+flexmenuid).length==1) //check flex menu is defined
			flexdropdownmenu.init($, $target, $('#'+flexmenuid))
	})
};

//By default, add flex menu to anchor links with attribute "data-flexmenu"
jQuery(document).ready(function($){
	var $anchors=$('*[data-flexmenu]')
	$anchors.each(function(){
		$(this).addflexmenu(this.getAttribute('data-flexmenu'))
	})
})


//ddlistmenu: Function to define a UL list menu dynamically

function ddlistmenu(id, className){
	var menu=document.createElement('ul')
	if (id)
		menu.id=id
	if (className)
		menu.className=className
	this.menu=menu
}

ddlistmenu.prototype={
	addItem:function(url, text, target){
		var li=document.createElement('li')
		li.innerHTML='<a href="'+url+'" target="'+target+'">'+text+'</a>'
		this.menu.appendChild(li)
		this.li=li
		return this
	},
	addSubMenu:function(){
		var s=new ddlistmenu(null, null)
		this.li.appendChild(s.menu)
		return s

	}
}
