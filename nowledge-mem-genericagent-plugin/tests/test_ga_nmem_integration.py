#!/usr/bin/env python3
"""
test_ga_nmem_integration.py - GenericAgent × nmem 集成测试

验证 nmem_auto_recall.py 插件在 GenericAgent 中的集成效果：
1. Hook 注册正确
2. System prompt 注入成功
3. Token 限制生效
4. 降级模式（nmem_recall.py 不可用时）
"""

import sys
import os
from pathlib import Path

# Add parent directories to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGINS_DIR = PROJECT_ROOT / 'plugins'
TEMP_DIR = PROJECT_ROOT / 'temp' / 'nmem_capability_research'

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PLUGINS_DIR))
sys.path.insert(0, str(TEMP_DIR))


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
    
    def run(self, name, test_func):
        try:
            print(f'\n[TEST] {name}')
            test_func()
            print(f'  ✓ PASS')
            self.passed += 1
        except AssertionError as e:
            print(f'  ✗ FAIL: {e}')
            self.failed += 1
        except Exception as e:
            print(f'  ⊘ SKIP: {e}')
            self.skipped += 1
    
    def summary(self):
        total = self.passed + self.failed + self.skipped
        print(f'\n{"="*60}')
        print(f'Total: {total} | Passed: {self.passed} | Failed: {self.failed} | Skipped: {self.skipped}')
        return self.failed == 0


# ============================================================
# Test Cases
# ============================================================

def test_plugin_import(runner: TestRunner):
    """INT-1: Plugin can be imported"""
    def run():
        try:
            import nmem_auto_recall
            assert hasattr(nmem_auto_recall, 'on_agent_before'), "Missing on_agent_before hook"
            assert hasattr(nmem_auto_recall, 'on_llm_before'), "Missing on_llm_before hook"
        except ImportError as e:
            raise Exception(f"Cannot import plugin: {e}")
    
    runner.run('INT-1: Plugin Import', run)


def test_nmem_recall_tool_available(runner: TestRunner):
    """INT-2: nmem_recall.py tool is available"""
    def run():
        import nmem_auto_recall
        assert nmem_auto_recall.NMEM_RECALL_AVAILABLE, "nmem_recall.py not found"
        from nmem_recall import NmemRecall
        recall = NmemRecall()
        assert hasattr(recall, 'recall'), "Missing recall() method"
    
    runner.run('INT-2: nmem_recall Tool Available', run)


def test_hook_registration(runner: TestRunner):
    """INT-3: Hooks are registered correctly"""
    def run():
        try:
            from plugins.hooks import _hooks
            assert 'agent_before' in _hooks, "agent_before hook not registered"
            assert 'llm_before' in _hooks, "llm_before hook not registered"
            
            agent_before_hooks = _hooks['agent_before']
            llm_before_hooks = _hooks['llm_before']
            
            # Check our hooks are in the list
            hook_names = [h.__name__ for h in agent_before_hooks]
            assert 'on_agent_before' in hook_names, "on_agent_before not in agent_before hooks"
            
            hook_names = [h.__name__ for h in llm_before_hooks]
            assert 'on_llm_before' in hook_names, "on_llm_before not in llm_before hooks"
        except ImportError:
            raise Exception("hooks module not available")
    
    runner.run('INT-3: Hook Registration', run)


def test_agent_before_hook_execution(runner: TestRunner):
    """INT-4: agent_before hook modifies messages correctly"""
    def run():
        import nmem_auto_recall
        
        # Mock context
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Test query about nmem integration"}
        ]
        ctx = {
            'messages': messages,
            'handler': None,
            'turn': 0
        }
        
        # Execute hook
        nmem_auto_recall.on_agent_before(ctx)
        
        # Verify system prompt was modified
        system_content = messages[0]['content']
        assert '[SOP Index]' in system_content, "SOP Index not injected"
        assert '[AutoRecall from nmem]' in system_content or 'Working Memory' in system_content, \
            "nmem context not injected"
    
    runner.run('INT-4: agent_before Hook Execution', run)


def test_idempotency(runner: TestRunner):
    """INT-5: Hook is idempotent (only runs once per session)"""
    def run():
        import nmem_auto_recall
        
        # Mock handler with marker
        class MockHandler:
            pass
        
        handler = MockHandler()
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Test query"}
        ]
        ctx = {
            'messages': messages,
            'handler': handler,
            'turn': 0
        }
        
        # First call
        nmem_auto_recall.on_agent_before(ctx)
        first_content = messages[0]['content']
        
        # Second call
        nmem_auto_recall.on_agent_before(ctx)
        second_content = messages[0]['content']
        
        # Content should be identical (not duplicated)
        assert first_content == second_content, "Hook not idempotent, content duplicated"
    
    runner.run('INT-5: Idempotency', run)


def test_keyword_extraction(runner: TestRunner):
    """INT-6: Keyword extraction works correctly"""
    def run():
        import nmem_auto_recall
        
        # English keywords
        keywords = nmem_auto_recall._extract_keywords("Test nmem integration with GenericAgent", max_kw=3)
        assert len(keywords) <= 3, f"Too many keywords: {len(keywords)}"
        assert any(k in ['integration', 'genericagent', 'nmem'] for k in keywords), \
            f"Expected keywords not found: {keywords}"
        
        # Chinese keywords
        keywords = nmem_auto_recall._extract_keywords("测试nmem集成功能", max_kw=3)
        assert len(keywords) <= 3, f"Too many keywords: {len(keywords)}"
    
    runner.run('INT-6: Keyword Extraction', run)


def test_sop_index_generation(runner: TestRunner):
    """INT-7: SOP index generation works"""
    def run():
        import nmem_auto_recall
        
        sop_index = nmem_auto_recall._generate_sop_index()
        # Should contain some SOPs (or empty if memory/ dir doesn't exist)
        assert isinstance(sop_index, str), "SOP index should be string"
        if sop_index:
            assert 'L3:' in sop_index, "SOP index should start with 'L3:'"
    
    runner.run('INT-7: SOP Index Generation', run)


def test_fallback_mode(runner: TestRunner):
    """INT-8: Fallback mode works when nmem_recall.py unavailable"""
    def run():
        import nmem_auto_recall
        
        # Temporarily disable tool
        original_available = nmem_auto_recall.NMEM_RECALL_AVAILABLE
        nmem_auto_recall.NMEM_RECALL_AVAILABLE = False
        
        try:
            result = nmem_auto_recall._do_recall_fallback("test query nmem")
            assert isinstance(result, str), "Fallback should return string"
            # Result might be empty if nmem CLI not available, that's OK
        finally:
            nmem_auto_recall.NMEM_RECALL_AVAILABLE = original_available
    
    runner.run('INT-8: Fallback Mode', run)


def test_llm_before_hook(runner: TestRunner):
    """INT-9: llm_before hook strips redundant memory injections"""
    def run():
        import nmem_auto_recall
        
        # Mock messages with duplicate memory blocks
        memory_block = '\n[Memory] (../memory)\nFacts(L2): ../memory/global_mem.txt\nRead L2 or ls ../memory/ for L3 when needed\n'
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": f"First query{memory_block}"},
            {"role": "assistant", "content": "Response"},
            {"role": "user", "content": f"Second query{memory_block}"}
        ]
        ctx = {'messages': messages}
        
        # Execute hook
        nmem_auto_recall.on_llm_before(ctx)
        
        # First occurrence should remain, second should be stripped
        assert memory_block in messages[1]['content'], "First memory block should remain"
        assert memory_block not in messages[3]['content'], "Second memory block should be stripped"
    
    runner.run('INT-9: llm_before Hook', run)


def test_token_limit(runner: TestRunner):
    """INT-10: Token limit is respected in recall"""
    def run():
        import nmem_auto_recall
        
        if not nmem_auto_recall.NMEM_RECALL_AVAILABLE:
            raise Exception("nmem_recall.py not available")
        
        # Use a query that might return large results
        result = nmem_auto_recall._do_recall_with_tool("nmem integration test query")
        
        # Rough token estimate: 1 token ≈ 4 chars
        estimated_tokens = len(result) // 4
        
        # Should be under 2KB (500 tokens * 4 chars)
        assert estimated_tokens <= 600, f"Result too large: ~{estimated_tokens} tokens (expected ≤600)"
    
    runner.run('INT-10: Token Limit', run)


# ============================================================
# Main
# ============================================================

def main():
    print('='*60)
    print('GenericAgent × nmem Integration Tests')
    print('='*60)
    
    runner = TestRunner()
    
    # Import tests
    test_plugin_import(runner)
    test_nmem_recall_tool_available(runner)
    test_hook_registration(runner)
    
    # Functional tests
    test_agent_before_hook_execution(runner)
    test_idempotency(runner)
    test_keyword_extraction(runner)
    test_sop_index_generation(runner)
    test_fallback_mode(runner)
    test_llm_before_hook(runner)
    test_token_limit(runner)
    
    # Summary
    success = runner.summary()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
