import i18n from '@/i18n'

const zh = {
  exporting: '正在导出…', cacheSaving: '正在保存缓存…',
  translate: '开始翻译', polish: '开始润色', polishing: '润色中', resume: '继续任务', stop: '停止任务', analysis: '开始分析', completed: '已完成', failed: '任务失败',
  costDetail: '平台未提供费用数据', stopped: '已停止，可以继续', noProject: '请先打开项目',
  errors: {
    operation_busy: '任务仍在运行或收尾，请稍候。', no_project: '请先打开项目。', project_not_open: '请先打开项目。',
    platform_not_configured: '请先在接口管理中为此任务绑定平台。', no_platform: '请先配置并绑定平台。',
    no_translated_items: '请先完成翻译后再润色。', task_failed: '任务执行失败，请查看日志。',
    no_task_to_continue: '当前没有可以继续的任务。', task_cannot_continue: '没有可恢复的任务统计，请开始新任务。',
    task_service_unavailable: '任务服务正在关闭或尚未就绪，请重新连接。',
    task_no_pending_items: '当前没有可处理的条目：翻译需要待译条目，润色需要已译条目。',
    task_platform_required: '请先在接口管理中为此任务绑定平台。', task_start_failed: '任务启动失败，请重试。',
    task_execution_failed: '任务执行失败，请检查接口、提示词和日志后重试。',
    cache_save_failed: '项目缓存保存失败，请检查目录权限和剩余磁盘空间。',
    project_input_path_missing: '项目缺少原始输入路径，请重新打开项目。', export_path_invalid: '请选择有效的输出文件夹。',
    export_conversion_failed: '简繁转换失败，已取消导出，请检查转换设置。',
    export_failed: '导出失败，请检查输入文件、输出目录权限和剩余磁盘空间。',
    request: '操作失败，请检查连接和任务配置后重试。',
  },
  exportTitle: '导出项目', exportDetail: '使用原有格式与输出设置生成译文和双语文件。', output: '输出文件夹', outputHint: '留空时使用输出设置中的路径。', browse: '浏览目录', export: '导出译文', saveCache: '保存项目缓存', cacheSaved: '项目缓存已保存', exported: '导出完成', files: '本次写入的文件', noFiles: '没有生成文件，请检查项目内容与输出设置。',
}
const en = {
  exporting: 'Exporting…', cacheSaving: 'Saving cache…',
  translate: 'Start translation', polish: 'Start polishing', polishing: 'Polishing', resume: 'Continue task', stop: 'Stop task', analysis: 'Start analysis', completed: 'Completed', failed: 'Task failed',
  costDetail: 'No cost data supplied by this platform', stopped: 'Stopped; ready to continue', noProject: 'Open a project first',
  errors: {
    operation_busy: 'A task is still running or finishing. Please wait.', no_project: 'Open a project first.', project_not_open: 'Open a project first.',
    platform_not_configured: 'Assign a platform for this task in API platforms.', no_platform: 'Configure and assign a platform first.',
    no_translated_items: 'Translate the project before polishing.', task_failed: 'The task failed. Check the logs.',
    no_task_to_continue: 'There is no task to continue.', task_cannot_continue: 'No saved task statistics are available. Start a new task.',
    task_service_unavailable: 'The task service is shutting down or unavailable. Reconnect and try again.',
    task_no_pending_items: 'No eligible items remain: translation needs untranslated items, and polishing needs translated items.',
    task_platform_required: 'Assign a platform for this task in API platforms.', task_start_failed: 'The task could not start. Try again.',
    task_execution_failed: 'The task failed. Check the platform, prompts, and logs before retrying.',
    cache_save_failed: 'Could not save the project cache. Check directory permissions and available disk space.',
    project_input_path_missing: 'The original input path is missing. Open the project again.', export_path_invalid: 'Choose a valid output folder.',
    export_conversion_failed: 'Chinese character conversion failed and export was cancelled. Check conversion settings.',
    export_failed: 'Export failed. Check the source files, output directory permissions, and available disk space.',
    request: 'The operation failed. Check your connection and task settings.',
  },
  exportTitle: 'Export project', exportDetail: 'Write translations and bilingual files using the original formats and your output preferences.', output: 'Output folder', outputHint: 'Leave blank to use your output settings.', browse: 'Browse folders', export: 'Export translations', saveCache: 'Save project cache', cacheSaved: 'Project cache saved', exported: 'Export complete', files: 'Files written', noFiles: 'No files were produced. Check the project and output settings.',
}
i18n.addResourceBundle('zh-CN', 'tasks', zh)
i18n.addResourceBundle('en', 'tasks', en)
export function taskErrorKey(code: string) { return `errors.${code in zh.errors ? code : 'request'}` }
