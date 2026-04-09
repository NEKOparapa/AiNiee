import concurrent.futures
import os
from collections import defaultdict

from ModuleFolders.Base.Base import Base
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester
from ModuleFolders.Infrastructure.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.Domain.ResponseExtractor.ResponseExtractor import ResponseExtractor
from ModuleFolders.Domain.ResponseChecker.ResponseChecker import ResponseChecker
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus


class ProofreadTask(LogMixin, Base):
    MAX_LINES = 20

    def __init__(self, task_data: dict, set_active_executor, clear_active_executor) -> None:
        super().__init__()
        self.task_data = task_data or {}
        self._set_active_executor = set_active_executor
        self._clear_active_executor = clear_active_executor
        self.config = TaskConfig()
        self.response_checker = ResponseChecker()

    def run(self) -> None:
        try:
            proofread_jobs = self._normalize_jobs(self.task_data)
            if not proofread_jobs:
                self._finish()
                return

            self.config.initialize()
            self.config.prepare_for_active_platform()

            batches = self._build_batches(proofread_jobs)
            if not batches:
                self._finish()
                return

            total_items = sum(len(job["items_to_proofread"]) for job in proofread_jobs)
            self.info(f" Starting table AI proofreading task: {len(proofread_jobs)} file(s), {total_items} rows")
            self.info(f"    Total batches: {len(batches)}")
            self.info(f"    Concurrent workers: {self.config.actual_thread_counts} (UI will refresh after task completion)")

            updates_by_file = defaultdict(dict)
            success_batches = 0
            failed_batches = 0

            executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.config.actual_thread_counts,
                thread_name_prefix="proofreader",
            )
            self._set_active_executor(executor)

            try:
                futures = []
                for batch in batches:
                    if Base.work_status == Base.STATUS.STOPING:
                        break

                    try:
                        futures.append(executor.submit(self._run_batch, batch))
                    except RuntimeError:
                        if Base.work_status == Base.STATUS.STOPING:
                            break
                        raise

                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                    except concurrent.futures.CancelledError:
                        continue
                    except Exception as error:
                        self.error(f"Proofreading batch execution error: {error}")
                        failed_batches += 1
                        continue

                    if not result:
                        failed_batches += 1
                        continue

                    success_batches += 1
                    file_path = result.get("file_path")
                    updated_items = result.get("updated_items", {})
                    if file_path and updated_items:
                        updates_by_file[file_path].update(updated_items)
            finally:
                try:
                    executor.shutdown(wait=True, cancel_futures=Base.work_status == Base.STATUS.STOPING)
                finally:
                    self._clear_active_executor(executor)

            self.info(f" Proofreading batches completed. Success: {success_batches}, Failed: {failed_batches}")
            self._emit_updates(updates_by_file)
            self._finish()
        except Exception as error:
            self.error(f"Table proofreading task failed: {error}", error)
            Base.work_status = Base.STATUS.IDLE
            raise

    def _normalize_jobs(self, data: dict) -> list[dict]:
        proofread_jobs = data.get("proofread_jobs")
        if not isinstance(proofread_jobs, list):
            file_path = data.get("file_path")
            items_to_proofread = data.get("items_to_proofread")
            if file_path and isinstance(items_to_proofread, list):
                proofread_jobs = [
                    {
                        "file_path": file_path,
                        "items_to_proofread": items_to_proofread,
                    }
                ]
            else:
                proofread_jobs = []

        normalized_jobs = []
        for job in proofread_jobs:
            if not isinstance(job, dict):
                continue

            file_path = job.get("file_path")
            items_to_proofread = job.get("items_to_proofread")
            if not file_path or not isinstance(items_to_proofread, list):
                continue

            normalized_items = []
            for item in items_to_proofread:
                if not isinstance(item, dict):
                    continue

                text_index = item.get("text_index")
                source_text = item.get("source_text", "")
                if text_index is None or source_text is None:
                    continue

                normalized_items.append(
                    {
                        "text_index": text_index,
                        "source_text": str(source_text),
                        "translation_text": str(item.get("translation_text", "") or ""),
                        "error_type": str(item.get("error_type", "") or ""),
                    }
                )

            if normalized_items:
                normalized_jobs.append(
                    {
                        "file_path": file_path,
                        "items_to_proofread": normalized_items,
                    }
                )

        return normalized_jobs

    def _build_batches(self, proofread_jobs: list[dict]) -> list[dict]:
        batches = []
        for job in proofread_jobs:
            file_path = job["file_path"]
            items_to_proofread = job["items_to_proofread"]
            total_batches = (len(items_to_proofread) + self.MAX_LINES - 1) // self.MAX_LINES

            self.info(f" Preparing proofreading batches for {os.path.basename(file_path)}")
            self.info(f"    Total rows: {len(items_to_proofread)}, batches: {total_batches}")

            for batch_idx in range(total_batches):
                start_index = batch_idx * self.MAX_LINES
                end_index = start_index + self.MAX_LINES
                batches.append(
                    {
                        "file_path": file_path,
                        "batch_idx": batch_idx,
                        "total_batches": total_batches,
                        "items": items_to_proofread[start_index:end_index],
                    }
                )

        return batches

    def _run_batch(self, batch: dict) -> dict | None:
        if Base.work_status == Base.STATUS.STOPING:
            return None

        file_path = batch["file_path"]
        batch_idx = batch["batch_idx"]
        total_batches = batch["total_batches"]
        batch_items = batch["items"]
        batch_num = batch_idx + 1

        current_platform_config = self.config.get_active_platform_configuration()
        source_text_dict = {str(idx): item["source_text"] for idx, item in enumerate(batch_items)}
        index_map = [item["text_index"] for item in batch_items]
        messages, system_prompt = self._build_table_proofread_prompt(batch_items)

        print(
            f" -> [Proofread {os.path.basename(file_path)} {batch_num}/{total_batches}] "
            f"sending request ({len(batch_items)} rows)..."
        )

        requester = LLMRequester()
        skip, _, response_content, _, _ = requester.sent_request(
            messages,
            system_prompt,
            current_platform_config,
        )

        if skip:
            print(f" <- [Proofread {os.path.basename(file_path)} {batch_num}/{total_batches}] request failed")
            return None

        response_dict = ResponseExtractor.text_extraction(self, source_text_dict, response_content)
        check_result, _ = self.response_checker.check_polish_response_content(
            self.config,
            response_content,
            response_dict,
            source_text_dict,
        )

        if not check_result:
            print(f" <- [Proofread {os.path.basename(file_path)} {batch_num}/{total_batches}] validation failed")
            return None

        restored_response_dict = {
            index_map[int(temp_idx_str)]: text
            for temp_idx_str, text in response_dict.items()
        }
        updated_items = ResponseExtractor.remove_numbered_prefix(self, restored_response_dict)

        print(
            f" <- [Proofread {os.path.basename(file_path)} {batch_num}/{total_batches}] "
            f"completed ({len(updated_items)} rows)"
        )
        return {
            "file_path": file_path,
            "updated_items": updated_items,
        }

    def _build_table_proofread_prompt(self, batch_items: list[dict]) -> tuple[list[dict], str]:
        target_language = str(getattr(self.config, "target_language", "") or "").replace("_", " ")

        item_blocks = []
        for index, item in enumerate(batch_items, start=1):
            issue_type = item.get("error_type") or "Unspecified issue"
            source_text = item.get("source_text", "")
            translation_text = item.get("translation_text", "")
            translation_display = translation_text if translation_text else "[EMPTY]"
            item_blocks.append(
                f"{index}. Issue Type: {issue_type}\n"
                f"Source Text:\n{source_text}\n"
                f"Current Translation:\n{translation_display}"
            )

        system_prompt = (
            "You are a professional translation proofreader. "
            "You will receive an issue type, source text, and current translation for each item. "
            "Output only the corrected final translation for each item without explanations."
        )
        item_blocks_text = "\n\n".join(item_blocks)
        user_prompt = (
            f"Target language: {target_language or 'keep the language used by the current translation'}\n"
            "Please proofread each item below.\n"
            "Requirements:\n"
            "1. Output only the corrected translation. Do not explain and do not repeat the source text.\n"
            "2. Preserve placeholders, variables, tags, escape sequences, line breaks, and special formatting.\n"
            "3. If the current translation is empty, missing, or clearly does not satisfy the issue type, translate directly from the source text.\n"
            "4. If the issue type mentions terminology, exclusion markers, line breaks, or placeholders, fix those issues first.\n"
            "5. Keep the output order exactly the same as the input order.\n"
            "Return the result strictly in this format:\n"
            "<textarea>\n"
            "1.Corrected translation\n"
            "2.Corrected translation\n"
            "</textarea>\n\n"
            "Items to proofread:\n"
            f"{item_blocks_text}"
        )

        return [{"role": "user", "content": user_prompt}], system_prompt

    def _emit_updates(self, updates_by_file: dict) -> None:
        for file_path, updated_items in updates_by_file.items():
            if not updated_items:
                continue

            self.info(f" Writing {len(updated_items)} proofreading results back to the table...")
            self.emit(
                Base.EVENT.TABLE_UPDATE,
                {
                    "file_path": file_path,
                    "target_column_index": 2,
                    "translation_status": TranslationStatus.POLISHED,
                    "updated_items": dict(updated_items),
                },
            )

    def _finish(self) -> None:
        if Base.work_status == Base.STATUS.STOPING:
            Base.work_status = Base.STATUS.TASKSTOPPED
            self.info(" Table AI proofreading task stopped")
        else:
            Base.work_status = Base.STATUS.IDLE
            self.info(" Table AI proofreading task finished")
