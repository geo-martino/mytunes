from functools import partial

import pytest

from mytunes.core.properties.logger import HasProgress
from tests.testers import BaseModelTester


class TestHasProgress:
    @pytest.fixture
    def model(self) -> HasProgress:
        return HasProgress()

    def test_run_tasks_sync_gets_results(self, model: HasProgress):
        tasks = [partial(lambda x: x, i) for i in range(10)]
        task_id = model._progress.add_task("Test", total=len(tasks))
    
        results = model._run_tasks(tasks, task_id=task_id, remove=False)
    
        assert task_id in model._progress.task_ids
        assert next(task for task in model._progress.tasks if task.id == task_id).completed
        assert len(results) == len(tasks)
        assert sorted(results) == [i for i in range(len(tasks))]

    def test_run_tasks_sync_removes_task(self, model: HasProgress):
        tasks = [partial(lambda x: x, i) for i in range(10)]
        task_id = model._progress.add_task("Test", total=len(tasks))
    
        model._run_tasks(tasks, task_id=task_id, remove=True)
        assert task_id not in model._progress.task_ids

    def test_run_tasks_sync_runs_without_task_id(self, model: HasProgress):
        tasks = [partial(lambda x: x, i) for i in range(10)]
    
        results = model._run_tasks(tasks)
    
        assert len(results) == len(tasks)
        assert sorted(results) == [i for i in range(len(tasks))]

    async def test_run_tasks_async_gets_results(self, model: HasProgress):
        async def _task(i: int) -> int:
            return i
    
        tasks = [_task(i) for i in range(10)]
        task_id = model._progress.add_task("Test", total=len(tasks))
    
        results = await model._run_tasks_async(tasks, task_id=task_id, remove=False)
    
        assert task_id in model._progress.task_ids
        assert next(task for task in model._progress.tasks if task.id == task_id).completed
        assert len(results) == len(tasks)
        assert sorted(results) == [i for i in range(len(tasks))]

    async def test_run_tasks_async_removes_task(self, model: HasProgress):
        async def _task(i: int) -> int:
            return i
    
        tasks = [_task(i) for i in range(10)]
        task_id = model._progress.add_task("Test", total=len(tasks))
    
        await model._run_tasks_async(tasks, task_id=task_id, remove=True)
        assert task_id not in model._progress.task_ids

    async def test_run_tasks_async_runs_without_task_id(self, model: HasProgress):
        async def _task(i: int) -> int:
            return i
    
        tasks = [_task(i) for i in range(10)]
    
        results = await model._run_tasks_async(tasks)
    
        assert len(results) == len(tasks)
        assert sorted(results) == [i for i in range(len(tasks))]
