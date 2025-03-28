// 此脚本用于在 RPG Maker MZ 和 MV 游戏中实现自动换行功能。
// 它会检查文本是否超出当前行的宽度，如果超出，则自动换行。

// 检查 RPG Maker 的版本 (MZ 或 MV)
if (Utils.RPGMAKER_NAME === "MZ") {

    // 重写 Window_Base.prototype.processCharacter 方法 (MZ 版本)
    Window_Base.prototype.processCharacter = function (textState) {
        const c = textState.text[textState.index++];  // 获取当前字符
        if (c.charCodeAt(0) < 0x20) {
            // 如果是控制字符（例如换行符、颜色代码等）
            this.flushTextState(textState);  // 刷新文本状态
            this.processControlCharacter(textState, c);  // 处理控制字符
        } else {
            // 如果是普通字符
            textState.buffer += c;  // 将字符添加到缓冲区
            if (textState.x + this.textWidth(c) >= this.innerWidth) {
                // 如果当前行的宽度加上当前字符的宽度超出了窗口的内部宽度
                this.processNewLine(textState);  // 换行
            }
        }
    };

} else {  // 如果是 MV

    // 重写 Window_Base.prototype.processNormalCharacter 方法 (MV 版本)
    Window_Base.prototype.processNormalCharacter = function(textState) {
        var c = textState.text[textState.index];  // 获取当前字符
        var w = this.textWidth(c);  // 获取当前字符的宽度
        if (this.width - 2 * this.standardPadding() - textState.x >= w){
            // 如果当前行的剩余宽度大于等于当前字符的宽度
            this.contents.drawText(c, textState.x, textState.y, w * 2, textState.height);  // 绘制字符
            textState.index++;  // 索引加 1
            textState.x += w;  // 更新当前行的 x 坐标
        } else {
            // 如果当前行的剩余宽度小于当前字符的宽度
            this.processNewLine(textState);  // 换行
            // 递归调用前增加出口条件, 避免无限循环
            if (textState.index < textState.text.length - 1) {
                textState.index--;  // 索引减1, 因为换行后，processNewLine方法已经把index加1了。
                this.processNormalCharacter(textState);  // 递归调用，处理换行后的字符
            }
        }
    };
    
}
