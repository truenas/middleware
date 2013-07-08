define(["dojo/json", "build/fs", "../build"], function(json, fs, buildModule){
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
				xstyleModuleInfo = bc.getSrcModuleInfo("xstyle/main", referenceModule, true),
				xstyleText = fs.readFileSync(xstyleModuleInfo.url + '.js', "utf8"),
				xstyleProcess = buildModule(xstyleText),
				layer = referenceModule.layer,
				targetStylesheet = layer && layer.targetStylesheet,
				targetStylesheetContents = layer && layer.targetStylesheetContents;
			if(targetStylesheet){
				// we want to calculate the target stylesheet relative to the layer
				var layerModule = bc.getSrcModuleInfo(referenceModule.layer.name, referenceModule, true);
				var targetStylesheetUrl = bc.getSrcModuleInfo(targetStylesheet, layerModule, true).url;
				// create a replacement function, to replace the stylesheet with combined stylesheet
				bc.replacements[targetStylesheetUrl] = [[function(){
					return targetStylesheetContents;
				}]];
				if(!targetStylesheetContents){
					// initialize the target stylesheet
					var targetStylesheetContents = '';
					try{
						var targetStylesheetContents = fs.readFileSync(targetStylesheetUrl, 'utf8');
					}catch(e){
						console.error(e);
					}
					// one target stylesheet per layer
					referenceModule.layer.targetStylesheetContents = targetStylesheetContents;
				}
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
			if(targetStylesheetUrl){
				// accumulate all the stylesheets in our target stylesheet
				var processed = processCss(cssResource);//, targetStylesheetUrl);
				targetStylesheetContents += processed.standardCss;
				referenceModule.layer.targetStylesheetContents = targetStylesheetContents;
			}
			else if(bc.internStrings && !bc.internSkip(stylesheetInfo.mid, referenceModule)){
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
						if(!this.processed){
							return ["url:" + this.mid, this.getText()];
						}else{
							return '';
						}
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
