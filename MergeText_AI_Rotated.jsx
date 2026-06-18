#target illustrator

/******************************
* @title MergeText_AI_Rotated
* @info Modified version to handle 90° rotated text
* @version 1.0.0
*******************************/

if(app.documents.length >= 1) {
	var doc = app.activeDocument;
	var sel = doc.selection;
	var tfs = new Array();
	var needsRotation = false;

	// 收集文本框
	for(var i=0; i < sel.length; i++){
		var t = sel[i];
		if (t == undefined) continue;
		if(t.typename == "TextFrame"){
			tfs.push(t);
			// 检查是否有旋转
			if(Math.abs(t.rotation) > 45 && Math.abs(t.rotation) < 135) {
				needsRotation = true;
			}
		}
	}

	if(tfs.length > 1) {
		// 如果检测到旋转，先旋转回来
		if(needsRotation) {
			for(var i=0; i < tfs.length; i++){
				tfs[i].rotate(-90);
			}
		}

		// 调用原始合并脚本
		var MERGE_TEXT_AI_QUICK = true;
		$.evalFile(new File($.fileName).parent.fsName + "/MergeText_AI.jsx");

		// 合并后旋转回去
		if(needsRotation) {
			var mergedText = doc.selection;
			if(mergedText.length > 0 && mergedText[0].typename == "TextFrame") {
				mergedText[0].rotate(90);
			}
		}
	} else if (tfs.length == 1) {
		alert("You must select more than one textfield.");
	} else {
		alert("No textfields selected.");
	}
} else {
	alert("No documents open");
}
