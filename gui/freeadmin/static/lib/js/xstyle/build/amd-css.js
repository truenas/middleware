define(["dojo/json", "build/fs", "../build"], function(json, fs, buildModule){
	var targetStylesheet, inLayer, targetDestStylesheetUrl, targetStylesheetContents = '';
	return {
		start:function(
			mid,
			referenceModule,
			bc
		){
			// mid may contain a pragma (e.g. "!strip"); remove
			mid = mid.split("!")[0];
			var cssPlugin = bc.amdResources["xstyle/css"],
				stylesheetInfo = bc.getSrcModuleInfo(mid, referenceModule, true),
				cssResource = bc.resources[stylesheetInfo.url],
				xstyleModuleInfo = bc.getSrcModuleInfo("xstyle/core/parser", referenceModule, true),
				xstyleText = fs.readFileSync(xstyleModuleInfo.url + '.js', "utf8"),
				xstyleProcess = buildModule(xstyleText),
				targetStylesheetUrl;		
				
			if(!bc.fixedUpLayersToDetect){
				bc.fixedUpLayersToDetect = true;
				for(var i in bc.layers){
					var layer = bc.layers[i];
					(function(layer){ 
						var oldInclude = layer.include;
						layer.include = {
							forEach: function(callback){
								// we want to calculate the target stylesheet relative to the layer
								inLayer = true;
								targetStylesheet = layer.targetStylesheet;
								if(targetStylesheet){
									var layerModule = bc.getSrcModuleInfo(layer.name);
									var targetStylesheetModule = bc.getSrcModuleInfo(targetStylesheet, layerModule, true);
									var targetDestStylesheetModule = bc.getDestModuleInfo(targetStylesheet, null, true);
									targetStylesheetModule.getText = function(){
										return targetStylesheetContents;
									};
									targetStylesheetUrl = targetStylesheetModule.url;
									targetDestStylesheetUrl = targetDestStylesheetModule.url;
									// initialize the target stylesheet
									targetStylesheetContents = '';
									try{
										targetStylesheetContents = fs.readFileSync(targetStylesheetUrl, 'utf8');
									}catch(e){
										console.error(e);
									}
								}
								oldInclude.forEach(callback);
							}
						};
					})(bc.layers[i]);
				}
			}
			if(targetStylesheet){
			}else{
				// there is no targe stylesheet, so
				// we will be directly inlining the stylesheet in the layer, so we need the createStyleSheet module
				var createStyleSheetModule = bc.getSrcModuleInfo('xstyle/util/createStyleSheet', referenceModule);
			}
			// read the stylesheet so we can process
			//var text= fs.readFileSync(stylesheetInfo.src, "utf8");

			if (!cssPlugin){
				throw new Error("text! plugin missing");
			}
			if (!cssResource){
				throw new Error("text resource (" + stylesheetInfo.url + ") missing");
			}

			var result = [cssPlugin];
			if(createStyleSheetModule){
				// if we are inlining the stylesheet, we need the functionality to insert a stylesheet from text 
				result.push(bc.amdResources['xstyle/util/createStyleSheet']);
			}
			if(bc.internStrings && !bc.internSkip(stylesheetInfo.mid, referenceModule)){
				// or inline it
				result.push({
					module:cssResource,
					pid:stylesheetInfo.pid,
					mid:stylesheetInfo.mid,
					deps:[],
					getText:function(){
						var processed = this.processed = processCss(this.module, true);//stylesheetInfo.url,  // inline resources too
						return processed.xstyleCss ?
							json.stringify({
								cssText: processed.standardCss,
								xCss: processed.xstyleCss
							}) :
							json.stringify(processed.standardCss +"");
					},
					internStrings:function(){
						if(targetStylesheet){
							// accumulate all the stylesheets in our target stylesheet
							var processed = processCss(this.module);//, targetStylesheetUrl);
							targetStylesheetContents += processed.standardCss;
							// in case the file doesn't exist
							//var targetDestStylesheetModule = bc.getDestModuleInfo(targetStylesheet, null, true);
							// the dojo buildcontrol module has a bug where it will leave the /x on the end of the string, have to remove it
							var url = targetDestStylesheetUrl.replace(/\/x$/,'');
							bc.log('writing stylesheet ' + url);
							
							fs.writeFileSync(url, targetStylesheetContents);
							return ['','0'];
						}
						if(inLayer){
							return ["url:" + this.mid, this.getText()];
						}
						return ['','0'];
					}
				});
			}
			function processCss(module, inlineAllResource){
				var text = module.getText ? module.getText() : module.text;
				if(text===undefined){
					// the module likely did not go through the read transform; therefore, just read it manually
					text= fs.readFileSync(this.module.src, "utf8");
				}
				var processed = xstyleProcess(text, stylesheetInfo.url, inlineAllResource);
				//for(var i = 0; i < processed.requiredModules.length; i++){
					// TODO: at some point, we may add an option to include the modules that
					// are required by the stylesheet, but at least by default these should 
					// probably be async lazy loaded
				//}
				return processed;
			}
			return result;
		}
	};
});
