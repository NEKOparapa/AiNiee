if (Utils.RPGMAKER_NAME === "MZ") {

    Window_Base.prototype.processCharacter = function (textState) {
        const c = textState.text[textState.index++];
        if (c.charCodeAt(0) < 0x20) {
            this.flushTextState(textState);
            this.processControlCharacter(textState, c);
        } else {
            textState.buffer += c;
            if (textState.x + this.textWidth(c) >= this.innerWidth) {
                this.processNewLine(textState);
            }
        }
    };

} else {

    Window_Base.prototype.processNormalCharacter = function(textState) {
        var c = textState.text[textState.index];
        var w = this.textWidth(c);
        if (this.width - 2 * this.standardPadding() - textState.x >= w){
            this.contents.drawText(c, textState.x, textState.y, w * 2, textState.height);
            textState.index++;
            textState.x += w;
        } else {
            this.processNewLine(textState);
            // 递归调用前增加出口条件
            if (textState.index < textState.text.length - 1) {
                textState.index--;
                this.processNormalCharacter(textState);
            }
        }
    };
    
}
