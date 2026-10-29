import i18n from '@/i18n'

const zh = {
  first: '第一页', last: '最后一页',
  title: '条目校对', description: '筛选文本、检查上下文，并直接修订原文与译文。', file: '文件', allFiles: '全部文件', status: '翻译状态', allStatus: '全部状态', search: '搜索原文与译文', regex: '正则表达式', flagged: '仅看语言标记', apply: '筛选', reset: '重置', source: '原文', translation: '译文', line: '条目', edit: '编辑{{field}}', save: '保存', cancel: '取消', saving: '正在保存…', empty: '没有符合条件的条目', noProject: '先打开一个项目，即可校对译文。', openProject: '打开项目', select: '选择条目 {{index}}', selectPage: '选择当前页', selected: '已选 {{count}} 条', clear: '取消选择', previous: '上一页', next: '下一页', pagination: '第 {{page}} / {{pages}} 页 · 共 {{total}} 条', loading: '正在读取条目…', retry: '重试', highlighted: '当前质量问题', saved: '条目已保存', jumpMissing: '该条目已不在当前页。请重新运行检查，更新定位信息。', editHint: '点击文字可编辑，Ctrl+Enter 保存，Esc 取消。',
  states: { '0': '未翻译', '1': '已翻译', '2': '已润色', '7': '已排除', '8': '存疑' },
  errors: { item_regex_invalid: '正则表达式无效，请检查后重试。', item_not_found: '条目不存在，项目可能已发生变化。', item_source_empty: '原文不能为空。', item_save_failed: '缓存保存失败，请检查磁盘权限和可用空间。', operation_busy: '任务运行期间无法修改条目或运行检查，请等待任务结束。', project_not_open: '请先打开项目。', fallback: '操作失败，请检查连接后重试。' },
}
const en = {
  first: 'First page', last: 'Last page',
  title: 'Proofreading', description: 'Filter text, review context and edit source or translation in place.', file: 'File', allFiles: 'All files', status: 'Translation status', allStatus: 'All statuses', search: 'Search source and translation', regex: 'Regular expression', flagged: 'Language flags only', apply: 'Filter', reset: 'Reset', source: 'Source', translation: 'Translation', line: 'Item', edit: 'Edit {{field}}', save: 'Save', cancel: 'Cancel', saving: 'Saving…', empty: 'No matching items', noProject: 'Open a project to start proofreading.', openProject: 'Open project', select: 'Select item {{index}}', selectPage: 'Select current page', selected: '{{count}} selected', clear: 'Clear selection', previous: 'Previous', next: 'Next', pagination: 'Page {{page}} / {{pages}} · {{total}} items', loading: 'Loading items…', retry: 'Retry', highlighted: 'Current quality issue', saved: 'Item saved', jumpMissing: 'This item is no longer on this page. Run the check again to refresh its location.', editHint: 'Click text to edit. Ctrl+Enter saves; Esc cancels.',
  states: { '0': 'Untranslated', '1': 'Translated', '2': 'Polished', '7': 'Excluded', '8': 'Questionable' },
  errors: { item_regex_invalid: 'The regular expression is invalid.', item_not_found: 'This item no longer exists. The project may have changed.', item_source_empty: 'Source text cannot be empty.', item_save_failed: 'Unable to save the cache. Check disk permissions and free space.', operation_busy: 'Wait for the current task to finish before editing or checking items.', project_not_open: 'Open a project first.', fallback: 'The operation failed. Check the connection and retry.' },
}
i18n.addResourceBundle('zh-CN', 'items', zh, true, true)
i18n.addResourceBundle('en', 'items', en, true, true)
i18n.addResourceBundle('zh-CN', 'items', { reload: '重新加载项目', errors: { project_changed: '当前项目已在其他页面切换，请重新加载后再修改。' } }, true, true)
i18n.addResourceBundle('en', 'items', { reload: 'Reload project', errors: { project_changed: 'The project changed in another page. Reload before editing.' } }, true, true)
