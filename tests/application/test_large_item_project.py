"""Large-project paging uses the real cache objects and preserves query semantics."""

from time import perf_counter

import pytest

from ModuleFolders.Application.ItemService import ItemService
from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem
from ModuleFolders.Service.Cache.CacheManager import CacheManager
from ModuleFolders.Service.Cache.CacheProject import CacheProject


@pytest.fixture
def large_items():
    manager = CacheManager()
    manager.load_from_project(CacheProject(
        project_id="large-items", project_name="Large project", project_type="Txt",
        files={name: CacheFile(storage_path=name, file_project_type="Txt", items=[
            CacheItem(text_index=(start + offset) * 2, source_text=f"Source {start + offset:05d}",
                      translated_text=f"Translation {start + offset:05d}" if offset % 2 else "",
                      translation_status=offset % 2,
                      extra={"language_mismatch_translation": offset % 100 == 0})
            for offset in range(25000)
        ]) for name, start in (("first.txt", 0), ("nested/last.txt", 25000))},
    ))
    yield ItemService(manager)
    manager._cleanup_event_subscriptions()


def test_large_project_first_last_and_cross_file_pages(large_items, record_property):
    start = perf_counter()
    first = large_items.list_items(page=1)
    last = large_items.list_items(page=500)
    cross_file = large_items.list_items(page=253, size=99)
    elapsed = perf_counter() - start
    record_property("unfiltered_three_page_ms", round(elapsed * 1000, 3))
    assert first["total"] == last["total"] == cross_file["total"] == 50000
    assert len(first["items"]) == len(last["items"]) == 100
    assert first["items"][0]["source_text"] == "Source 00000"
    assert last["items"][-1]["source_text"] == "Source 49999"
    assert last["items"][-1]["index"] == 99998
    assert last["items"][-1]["position"] == 24999
    # This page straddles the file boundary and must keep per-file positions.
    assert cross_file["items"][0]["file"] == "first.txt"
    assert cross_file["items"][0]["position"] == 24948
    assert cross_file["items"][52]["file"] == "nested/last.txt"
    assert cross_file["items"][52]["position"] == 0
    assert large_items.list_items(page=501)["items"] == []
    assert elapsed < 3, "Paging small responses should not freeze on a 50,000-item project"


def test_large_project_filters_keep_totals_order_and_stable_identity(large_items, record_property):
    start = perf_counter()
    file_page = large_items.list_items(file="nested/last.txt", page=250)
    filtered = large_items.list_items(status=1, page=250)
    found = large_items.list_items(q="49999")
    flagged = large_items.list_items(flagged=True, page=5)
    regex = large_items.list_items(q=r"^Source 4999[0-9]$", regex=True)
    elapsed = perf_counter() - start
    record_property("filtered_queries_ms", round(elapsed * 1000, 3))
    assert file_page["total"] == filtered["total"] == 25000
    assert file_page["items"][-1]["source_text"] == "Source 49999"
    assert found["total"] == 1 and found["items"][0]["index"] == 99998
    assert flagged["total"] == 500 and len(flagged["items"]) == 100
    assert regex["total"] == 10
    assert [row["source_text"] for row in regex["items"]] == [f"Source {index}" for index in range(49990, 50000)]
    assert elapsed < 5, "Local filters should remain responsive on a 50,000-item project"
