// ReleaseClippingMask.jsx
// 释放选中的剪切蒙版

if (app.documents.length > 0) {
    var doc = app.activeDocument;
    var sel = doc.selection;

    if (sel.length > 0) {
        try {
            // 释放剪切蒙版的正确命令
            app.executeMenuCommand('releaseMask');
            // alert('已释放剪切蒙版');
        } catch (e) {
            alert('释放失败：' + e.message + '\n请确保选中的是剪切蒙版对象');
        }
    } else {
        alert('请先选中一个剪切蒙版对象');
    }
} else {
    alert('请先打开一个文档');
}
