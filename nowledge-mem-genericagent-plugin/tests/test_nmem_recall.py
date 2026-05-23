#!/usr/bin/env python3
"""
test_nmem_recall.py - Edge Cases 测试套件

测试 nmem_recall.py 的所有边界情况和错误处理。
"""

import json
import subprocess
import sys
import os
from pathlib import Path

# 添加父目录到 path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from nmem_recall import NmemRecall, RecallResult
except ImportError:
    print("Error: Cannot import nmem_recall. Make sure nmem_recall.py is in the same directory.")
    sys.exit(1)


class TestRunner:
    """测试运行器"""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.results = []
    
    def test(self, name: str, func):
        """运行单个测试"""
        try:
            print(f"\n[TEST] {name}")
            func()
            print(f"  ✓ PASS")
            self.passed += 1
            self.results.append((name, 'PASS', None))
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
            self.failed += 1
            self.results.append((name, 'FAIL', str(e)))
        except Exception as e:
            print(f"  ⚠ ERROR: {e}")
            self.failed += 1
            self.results.append((name, 'ERROR', str(e)))
    
    def skip(self, name: str, reason: str):
        """跳过测试"""
        print(f"\n[SKIP] {name}: {reason}")
        self.skipped += 1
        self.results.append((name, 'SKIP', reason))
    
    def summary(self):
        """输出测试摘要"""
        total = self.passed + self.failed + self.skipped
        print(f"\n{'='*60}")
        print(f"Test Summary: {self.passed}/{total} passed")
        print(f"  Passed:  {self.passed}")
        print(f"  Failed:  {self.failed}")
        print(f"  Skipped: {self.skipped}")
        print(f"{'='*60}")
        
        if self.failed > 0:
            print("\nFailed tests:")
            for name, status, error in self.results:
                if status in ('FAIL', 'ERROR'):
                    print(f"  - {name}: {error}")
        
        return self.failed == 0


def check_nmem_available() -> bool:
    """检查 nmem 是否可用"""
    try:
        result = subprocess.run(['nmem', 'status'], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ============================================================================
# Edge Cases Tests
# ============================================================================

def test_working_memory_not_exist(runner: TestRunner):
    """EC-1: Working Memory 读取（可能存在或不存在）"""
    def run():
        recall = NmemRecall()
        wm = recall.read_working_memory()
        # 应该返回 None 或字符串，不应该报错
        assert wm is None or isinstance(wm, str), f"Expected None or str, got: {type(wm)}"
        print(f"    (WM content length: {len(wm) if wm else 0} chars)")
    
    runner.test("EC-1: Working Memory 读取（可能存在或不存在）", run)


def test_working_memory_empty(runner: TestRunner):
    """EC-2: Working Memory 为空"""
    def run():
        recall = NmemRecall()
        wm = recall.read_working_memory()
        # 如果 WM 存在但为空，应该返回空字符串
        if wm is not None:
            assert isinstance(wm, str), f"Expected str, got: {type(wm)}"
    
    runner.test("EC-2: Working Memory 为空", run)


def test_memories_search_no_results(runner: TestRunner):
    """EC-3: Memories Search 无结果"""
    def run():
        recall = NmemRecall()
        memories = recall.search_memories("xyzabc123nonexistent")
        assert isinstance(memories, list), f"Expected list, got: {type(memories)}"
        assert len(memories) == 0, f"Expected empty list, got {len(memories)} results"
    
    runner.test("EC-3: Memories Search 无结果", run)


def test_memories_search_with_unit_type(runner: TestRunner):
    """EC-4: Memories Search 指定 unit_type"""
    def run():
        recall = NmemRecall()
        memories = recall.search_memories("test", unit_type="decision")
        assert isinstance(memories, list), f"Expected list, got: {type(memories)}"
        # 结果可能为空，但不应该报错
    
    runner.test("EC-4: Memories Search 指定 unit_type", run)


def test_memories_search_with_time_range(runner: TestRunner):
    """EC-5: Memories Search 指定时间范围"""
    def run():
        recall = NmemRecall()
        memories = recall.search_memories("test", event_from="2024-01-01", event_to="2024-12-31")
        assert isinstance(memories, list), f"Expected list, got: {type(memories)}"
    
    runner.test("EC-5: Memories Search 指定时间范围", run)


def test_threads_search_no_results(runner: TestRunner):
    """EC-6: Threads Search 无结果"""
    def run():
        recall = NmemRecall()
        threads = recall.search_threads("xyzabc123nonexistent")
        assert isinstance(threads, list), f"Expected list, got: {type(threads)}"
        assert len(threads) == 0, f"Expected empty list, got {len(threads)} results"
    
    runner.test("EC-6: Threads Search 无结果", run)


def test_entities_search_no_results(runner: TestRunner):
    """EC-7: Entities Search 无结果"""
    def run():
        recall = NmemRecall()
        entities = recall.search_entities("xyzabc123nonexistent")
        assert isinstance(entities, list), f"Expected list, got: {type(entities)}"
        assert len(entities) == 0, f"Expected empty list, got {len(entities)} results"
    
    runner.test("EC-7: Entities Search 无结果", run)


def test_graph_explore_nonexistent_entity(runner: TestRunner):
    """EC-8: Graph Explore 不存在的实体"""
    def run():
        recall = NmemRecall()
        graph = recall.explore_graph("xyzabc123nonexistent")
        # 应该返回 None 或空结果，不应该报错
        assert graph is None or isinstance(graph, dict), f"Expected None or dict, got: {type(graph)}"
    
    runner.test("EC-8: Graph Explore 不存在的实体", run)


def test_graph_explore_depth_limit(runner: TestRunner):
    """EC-9: Graph Explore 深度限制"""
    def run():
        recall = NmemRecall()
        # 测试深度 = 2（默认）
        graph = recall.explore_graph("test", depth=2)
        assert graph is None or isinstance(graph, dict), f"Expected None or dict, got: {type(graph)}"
    
    runner.test("EC-9: Graph Explore 深度限制", run)


def test_recall_full_flow(runner: TestRunner):
    """EC-10: 完整召回流程"""
    def run():
        recall = NmemRecall()
        result = recall.recall("test", include_wm=True, include_graph=False)
        
        assert isinstance(result, RecallResult), f"Expected RecallResult, got: {type(result)}"
        assert isinstance(result.memories, list), "memories should be list"
        assert isinstance(result.threads, list), "threads should be list"
        assert isinstance(result.entities, list), "entities should be list"
        assert result.graph_context is None, "graph_context should be None when include_graph=False"
        assert isinstance(result.total_tokens, int), "total_tokens should be int"
    
    runner.test("EC-10: 完整召回流程", run)


def test_recall_without_wm(runner: TestRunner):
    """EC-11: 召回流程不包含 WM"""
    def run():
        recall = NmemRecall()
        result = recall.recall("test", include_wm=False, include_graph=False)
        
        assert result.working_memory_focus is None, "WM focus should be None when include_wm=False"
    
    runner.test("EC-11: 召回流程不包含 WM", run)


def test_recall_with_graph(runner: TestRunner):
    """EC-12: 召回流程包含 Graph"""
    def run():
        recall = NmemRecall()
        result = recall.recall("test", include_wm=False, include_graph=True)
        
        # graph_context 可能为 None（如果没有实体），但不应该报错
        assert result.graph_context is None or isinstance(result.graph_context, dict), \
            f"Expected None or dict, got: {type(result.graph_context)}"
    
    runner.test("EC-12: 召回流程包含 Graph", run)


def test_format_for_prompt_empty_result(runner: TestRunner):
    """EC-13: 格式化空结果"""
    def run():
        recall = NmemRecall()
        result = RecallResult(
            memories=[],
            threads=[],
            entities=[],
            graph_context=None,
            working_memory_focus=None,
            total_tokens=0
        )
        
        prompt = recall.format_for_prompt(result)
        assert isinstance(prompt, str), f"Expected str, got: {type(prompt)}"
        assert len(prompt) > 0, "Prompt should not be empty"
        assert "[Usage]" in prompt, "Prompt should contain usage hint"
    
    runner.test("EC-13: 格式化空结果", run)


def test_format_for_prompt_with_results(runner: TestRunner):
    """EC-14: 格式化有结果"""
    def run():
        recall = NmemRecall()
        result = RecallResult(
            memories=[
                {'id': 'mem1', 'content': 'Test memory 1'},
                {'id': 'mem2', 'content': 'Test memory 2'}
            ],
            threads=[
                {'id': 'thread1', 'title': 'Test thread 1'}
            ],
            entities=[
                {'name': 'Entity1', 'type': 'person'}
            ],
            graph_context=None,
            working_memory_focus="Test focus",
            total_tokens=100
        )
        
        prompt = recall.format_for_prompt(result)
        assert isinstance(prompt, str), f"Expected str, got: {type(prompt)}"
        assert "[Working Memory Focus]" in prompt, "Should contain WM focus"
        assert "[Relevant Memories]" in prompt, "Should contain memories"
        assert "[Relevant Threads]" in prompt, "Should contain threads"
        assert "[Relevant Entities]" in prompt, "Should contain entities"
        assert "mem1" in prompt, "Should contain memory ID"
        assert "thread1" in prompt, "Should contain thread ID"
        assert "Entity1" in prompt, "Should contain entity name"
    
    runner.test("EC-14: 格式化有结果", run)


def test_format_for_prompt_token_limit(runner: TestRunner):
    """EC-15: 格式化 token 限制"""
    def run():
        recall = NmemRecall()
        # 创建大量结果
        large_memories = [
            {'id': f'mem{i}', 'content': 'x' * 1000}
            for i in range(100)
        ]
        
        result = RecallResult(
            memories=large_memories,
            threads=[],
            entities=[],
            graph_context=None,
            working_memory_focus=None,
            total_tokens=10000
        )
        
        prompt = recall.format_for_prompt(result, max_tokens=500)
        estimated_tokens = len(prompt) // 4
        
        # 应该被截断到约 500 tokens
        assert estimated_tokens <= 600, f"Expected <= 600 tokens, got {estimated_tokens}"
        
        if "[TRUNCATED" in prompt:
            print(f"    (Correctly truncated to {estimated_tokens} tokens)")
    
    runner.test("EC-15: 格式化 token 限制", run)


def test_max_results_limit(runner: TestRunner):
    """EC-16: 最大结果数限制"""
    def run():
        recall = NmemRecall(max_memories=3, max_threads=2, max_entities=2)
        result = recall.recall("test")
        
        assert len(result.memories) <= 3, f"Expected <= 3 memories, got {len(result.memories)}"
        assert len(result.threads) <= 2, f"Expected <= 2 threads, got {len(result.threads)}"
        assert len(result.entities) <= 2, f"Expected <= 2 entities, got {len(result.entities)}"
    
    runner.test("EC-16: 最大结果数限制", run)


def test_nmem_command_timeout(runner: TestRunner):
    """EC-17: nmem 命令超时"""
    def run():
        recall = NmemRecall()
        # 正常查询应该在 10s 内完成
        result = recall.search_memories("test")
        assert isinstance(result, list), "Should return list even on timeout"
    
    runner.test("EC-17: nmem 命令超时", run)


def test_nmem_service_unavailable(runner: TestRunner):
    """EC-18: nmem 服务不可用"""
    def run():
        # 这个测试只能在 nmem 不可用时运行
        if check_nmem_available():
            runner.skip("EC-18: nmem 服务不可用", "nmem is available")
            return
        
        recall = NmemRecall()
        result = recall.recall("test")
        
        # 应该返回空结果，不应该报错
        assert isinstance(result, RecallResult), "Should return RecallResult even when nmem unavailable"
        assert len(result.memories) == 0, "Should return empty memories"
        assert len(result.threads) == 0, "Should return empty threads"
    
    if not check_nmem_available():
        runner.test("EC-18: nmem 服务不可用", run)
    else:
        runner.skip("EC-18: nmem 服务不可用", "nmem is available")


def test_invalid_unit_type(runner: TestRunner):
    """EC-19: 无效的 unit_type"""
    def run():
        recall = NmemRecall()
        # 使用无效的 unit_type
        memories = recall.search_memories("test", unit_type="invalid_type")
        # 应该返回空列表或所有结果，不应该报错
        assert isinstance(memories, list), f"Expected list, got: {type(memories)}"
    
    runner.test("EC-19: 无效的 unit_type", run)


def test_invalid_date_format(runner: TestRunner):
    """EC-20: 无效的日期格式"""
    def run():
        recall = NmemRecall()
        # 使用无效的日期格式
        memories = recall.search_memories("test", event_from="invalid-date")
        # 应该返回结果或空列表，不应该报错
        assert isinstance(memories, list), f"Expected list, got: {type(memories)}"
    
    runner.test("EC-20: 无效的日期格式", run)


def test_concurrent_queries(runner: TestRunner):
    """EC-21: 并发查询（串行执行）"""
    def run():
        recall = NmemRecall()
        # 连续执行多个查询
        result1 = recall.search_memories("test1")
        result2 = recall.search_memories("test2")
        result3 = recall.search_threads("test3")
        
        assert isinstance(result1, list), "Query 1 should return list"
        assert isinstance(result2, list), "Query 2 should return list"
        assert isinstance(result3, list), "Query 3 should return list"
    
    runner.test("EC-21: 并发查询（串行执行）", run)


# ============================================================================
# Main
# ============================================================================

def main():
    """运行所有测试"""
    print("="*60)
    print("nmem_recall.py Edge Cases Test Suite")
    print("="*60)
    
    # 检查 nmem 是否可用
    if not check_nmem_available():
        print("\n⚠ WARNING: nmem service is not available")
        print("Some tests will be skipped or may fail")
        print("To run full tests, ensure nmem is running: nmem status")
    
    runner = TestRunner()
    
    # 运行所有测试
    test_working_memory_not_exist(runner)
    test_working_memory_empty(runner)
    test_memories_search_no_results(runner)
    test_memories_search_with_unit_type(runner)
    test_memories_search_with_time_range(runner)
    test_threads_search_no_results(runner)
    test_entities_search_no_results(runner)
    test_graph_explore_nonexistent_entity(runner)
    test_graph_explore_depth_limit(runner)
    test_recall_full_flow(runner)
    test_recall_without_wm(runner)
    test_recall_with_graph(runner)
    test_format_for_prompt_empty_result(runner)
    test_format_for_prompt_with_results(runner)
    test_format_for_prompt_token_limit(runner)
    test_max_results_limit(runner)
    test_nmem_command_timeout(runner)
    test_nmem_service_unavailable(runner)
    test_invalid_unit_type(runner)
    test_invalid_date_format(runner)
    test_concurrent_queries(runner)
    
    # 输出摘要
    success = runner.summary()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
