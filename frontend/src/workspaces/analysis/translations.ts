import i18n from '@/i18n'
const zh = {
  reloadConfirm: '重新加载会放弃未保存的修改，是否继续？',
  moveConfirm: '移动所选条目？目标中相同原文会被覆盖，原分类将保留在备注中。',
  title: '项目分析', description: '整理角色、术语与禁翻内容，为翻译提供项目上下文。', characters: '角色', terms: '术语', non_translate: '禁翻内容',
  start: '开始分析', startHint: '重新分析会更新分析结果，请先保存或导出需要保留的内容。', confirmStart: '开始新的项目分析？现有分析结果可能被替换。',
  source: '原文', marker: '标记', recommended_translation: '建议译文', gender: '性别', category_path: '分类', category: '分类', occurrence_count: '出现次数', note: '备注',
  save: '保存修改', saved: '修改已保存', dirty: '有未保存的修改', discard: '放弃修改', add: '新增条目', remove: '删除所选', removeConfirm: '删除所选分析条目？保存后生效。', all: '选择当前页', selected: '已选 {{count}} 条', empty: '暂无匹配内容，可开始分析、导入 JSON 或新增条目。',
  search: '搜索分析结果', allCategories: '全部分类', filterCategory: '筛选分类', import: '导入 JSON', export: '导出当前筛选', imported: '已新增 {{added}} 条，替换 {{replaced}} 条，跳过 {{skipped}} 条。',
  publish: '写入公共表格', publishTarget: '目标公共表', defaultTable: '当前表（没有时新建）', published: '已追加 {{count}} 条，已有原文保持不变。', move: '移动所选', moveCategory: '目标分类', toCharacters: '移至角色', toTerms: '移至术语', previous: '上一页', next: '下一页', page: '{{page}} / {{total}} 页', total: '{{count}} 条',
  saveFirst: '请先保存当前修改，再执行此操作。', noProject: '请先打开项目。', error: '操作失败，请检查连接、文件格式与任务状态后重试。', project_changed: '当前项目已切换，请重新加载分析结果。', operation_busy: '请等待当前任务结束。', file_too_large: '文件不能超过 20 MB。', reload: '重新加载',
}
const en = {
  reloadConfirm: 'Reloading will discard unsaved changes. Continue?',
  moveConfirm: 'Move the selected items? Matching sources in the target will be replaced. The original category will be kept in notes.',
  title: 'Project analysis', description: 'Organize characters, terms and exclusions to provide project context for translation.', characters: 'Characters', terms: 'Terms', non_translate: 'Exclusions',
  start: 'Start analysis', startHint: 'A new analysis updates these results. Save or export anything you need to keep.', confirmStart: 'Start a new analysis? Existing analysis results may be replaced.',
  source: 'Source', marker: 'Marker', recommended_translation: 'Suggested translation', gender: 'Gender', category_path: 'Category', category: 'Category', occurrence_count: 'Occurrences', note: 'Notes',
  save: 'Save changes', saved: 'Changes saved', dirty: 'Unsaved changes', discard: 'Discard changes', add: 'Add item', remove: 'Delete selected', removeConfirm: 'Delete selected analysis items? Save to apply.', all: 'Select current page', selected: '{{count}} selected', empty: 'No matching results. Run an analysis, import JSON or add an item.',
  search: 'Search analysis results', allCategories: 'All categories', filterCategory: 'Filter category', import: 'Import JSON', export: 'Export filtered rows', imported: '{{added}} added, {{replaced}} replaced, {{skipped}} skipped.',
  publish: 'Add to shared table', publishTarget: 'Target shared table', defaultTable: 'Current table (create if missing)', published: '{{count}} rows added. Existing sources were preserved.', move: 'Move selected', moveCategory: 'Target category', toCharacters: 'Move to characters', toTerms: 'Move to terms', previous: 'Previous', next: 'Next', page: 'Page {{page}} / {{total}}', total: '{{count}} items',
  saveFirst: 'Save the current changes before this operation.', noProject: 'Open a project first.', error: 'The operation failed. Check the connection, file format and task status.', project_changed: 'The project changed. Reload analysis results.', operation_busy: 'Wait for the current task to finish.', file_too_large: 'The file must be 20 MB or smaller.', reload: 'Reload',
}
i18n.addResourceBundle('zh-CN', 'analysis', zh)
i18n.addResourceBundle('en', 'analysis', en)
