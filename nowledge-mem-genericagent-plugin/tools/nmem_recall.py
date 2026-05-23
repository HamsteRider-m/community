#!/usr/bin/env python3
"""
nmem_recall.py - GenericAgent × nmem 历史经验召回工具

核心功能：
1. Memories Search - 主要历史经验召回
2. Threads Search - 会话历史召回
3. Entities Search - 实体关联召回
4. Graph Explore - 深度上下文扩展
5. Working Memory - 可选读取当前优先事项
"""

import json
import subprocess
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RecallResult:
    """召回结果"""
    memories: List[Dict[str, Any]]
    threads: List[Dict[str, Any]]
    entities: List[Dict[str, Any]]
    graph_context: Optional[Dict[str, Any]]
    working_memory_focus: Optional[str]
    total_tokens: int


class NmemRecall:
    """nmem 召回工具"""
    
    def __init__(self, max_memories: int = 10, max_threads: int = 5, max_entities: int = 5):
        self.max_memories = max_memories
        self.max_threads = max_threads
        self.max_entities = max_entities
        self.total_tokens = 0
    
    def _run_nmem_command(self, args: List[str]) -> Optional[Dict[str, Any]]:
        """执行 nmem 命令"""
        try:
            result = subprocess.run(
                ['nmem', '-j'] + args,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
            return None
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
            print(f"[nmem_recall] Error: {e}", file=sys.stderr)
            return None
    
    def search_memories(self, query: str, unit_type: Optional[str] = None, 
                       event_from: Optional[str] = None, event_to: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        搜索 memories（主要历史经验召回）
        
        Args:
            query: 搜索关键词
            unit_type: 可选，限制类型 (fact/preference/decision/plan/procedure/learning/context/event)
            event_from: 可选，事件开始时间 (YYYY-MM-DD)
            event_to: 可选，事件结束时间 (YYYY-MM-DD)
        """
        args = ['m', 'search', query, '-n', str(self.max_memories)]
        
        if unit_type:
            args.extend(['--unit-type', unit_type])
        if event_from:
            args.extend(['--event-from', event_from])
        if event_to:
            args.extend(['--event-to', event_to])
        
        result = self._run_nmem_command(args)
        if result and 'results' in result:
            memories = result['results']
            # 估算 token 数（粗略：每个字符 0.25 token）
            self.total_tokens += sum(len(json.dumps(m)) for m in memories) // 4
            return memories
        return []
    
    def search_threads(self, query: str) -> List[Dict[str, Any]]:
        """搜索 threads（会话历史召回）"""
        args = ['t', 'search', query, '-n', str(self.max_threads)]
        result = self._run_nmem_command(args)
        
        if result and 'results' in result:
            threads = result['results']
            self.total_tokens += sum(len(json.dumps(t)) for t in threads) // 4
            return threads
        return []
    
    def search_entities(self, query: str) -> List[Dict[str, Any]]:
        """搜索 entities（实体关联召回）"""
        args = ['e', 'search', query, '-n', str(self.max_entities)]
        result = self._run_nmem_command(args)
        
        if result and 'results' in result:
            entities = result['results']
            self.total_tokens += sum(len(json.dumps(e)) for e in entities) // 4
            return entities
        return []
    
    def explore_graph(self, entity_name: str, depth: int = 2) -> Optional[Dict[str, Any]]:
        """
        图谱扩展（深度上下文）
        
        Args:
            entity_name: 实体名称
            depth: 扩展深度（默认 2，避免过度扩展）
        """
        args = ['g', 'explore', entity_name, '--depth', str(depth)]
        result = self._run_nmem_command(args)
        
        if result:
            self.total_tokens += len(json.dumps(result)) // 4
            return result
        return None
    
    def read_working_memory(self) -> Optional[str]:
        """
        读取 Working Memory（可选）
        返回 Focus Areas 和 Briefing 的简洁摘要
        """
        try:
            result = subprocess.run(
                ['nmem', 'wm', 'read'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                wm_content = result.stdout
                # 提取 Focus Areas（简化版）
                focus = self._extract_focus_areas(wm_content)
                self.total_tokens += len(focus) // 4
                return focus
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"[nmem_recall] WM read error: {e}", file=sys.stderr)
            return None
    
    def _extract_focus_areas(self, wm_content: str) -> str:
        """从 Working Memory 提取 Focus Areas"""
        lines = wm_content.split('\n')
        focus_section = []
        in_focus = False
        
        for line in lines:
            if 'Focus Areas' in line:
                in_focus = True
                continue
            if in_focus:
                if line.strip().startswith('•'):
                    focus_section.append(line.strip())
                elif line.strip() and not line.strip().startswith('┃'):
                    # 遇到其他章节，停止
                    if len(focus_section) > 0:
                        break
        
        return '\n'.join(focus_section[:5])  # 最多 5 条
    
    def recall(self, query: str, include_wm: bool = True, 
               include_graph: bool = False, unit_type: Optional[str] = None) -> RecallResult:
        """
        完整召回流程
        
        Args:
            query: 搜索关键词
            include_wm: 是否包含 Working Memory
            include_graph: 是否包含 Graph Explore
            unit_type: 可选，限制 memory 类型
        """
        self.total_tokens = 0
        
        # 1. Working Memory（可选）
        wm_focus = None
        if include_wm:
            wm_focus = self.read_working_memory()
        
        # 2. Memories Search（主要）
        memories = self.search_memories(query, unit_type=unit_type)
        
        # 3. Threads Search
        threads = self.search_threads(query)
        
        # 4. Entities Search
        entities = self.search_entities(query)
        
        # 5. Graph Explore（可选）
        graph_context = None
        if include_graph and entities:
            top_entity = entities[0].get('name')
            if top_entity:
                graph_context = self.explore_graph(top_entity)
        
        return RecallResult(
            memories=memories,
            threads=threads,
            entities=entities,
            graph_context=graph_context,
            working_memory_focus=wm_focus,
            total_tokens=self.total_tokens
        )
    
    def format_for_prompt(self, result: RecallResult, max_tokens: int = 2000) -> str:
        """
        格式化为 prompt 注入内容（token efficient）
        
        Args:
            result: 召回结果
            max_tokens: 最大 token 数（默认 2000，约 8KB）
        """
        sections = []
        
        # 1. Working Memory Focus
        if result.working_memory_focus:
            sections.append(f"[Working Memory Focus]\n{result.working_memory_focus}\n")
        
        # 2. Top Memories
        if result.memories:
            mem_lines = ["[Relevant Memories]"]
            for i, mem in enumerate(result.memories[:5], 1):  # 最多 5 条
                mem_id = mem.get('id', 'unknown')
                content = mem.get('content', '')[:200]  # 最多 200 字符
                mem_lines.append(f"{i}. [{mem_id}] {content}...")
            sections.append('\n'.join(mem_lines) + '\n')
        
        # 3. Top Threads
        if result.threads:
            thread_lines = ["[Relevant Threads]"]
            for i, thread in enumerate(result.threads[:3], 1):  # 最多 3 条
                thread_id = thread.get('id', 'unknown')
                title = thread.get('title', 'Untitled')
                thread_lines.append(f"{i}. [{thread_id}] {title}")
            sections.append('\n'.join(thread_lines) + '\n')
        
        # 4. Top Entities
        if result.entities:
            entity_lines = ["[Relevant Entities]"]
            for i, entity in enumerate(result.entities[:5], 1):  # 最多 5 条
                name = entity.get('name', 'unknown')
                entity_type = entity.get('type', 'unknown')
                entity_lines.append(f"{i}. {name} ({entity_type})")
            sections.append('\n'.join(entity_lines) + '\n')
        
        # 5. 使用提示
        sections.append("[Usage]\nUse `nmem m show <id>` or `nmem t show <id>` to read full content.\n")
        
        prompt_content = '\n'.join(sections)
        
        # Token 限制检查
        estimated_tokens = len(prompt_content) // 4
        if estimated_tokens > max_tokens:
            # 截断到 max_tokens
            prompt_content = prompt_content[:max_tokens * 4]
            prompt_content += "\n[TRUNCATED - use nmem CLI for full content]"
        
        return prompt_content


def main():
    """CLI 入口"""
    if len(sys.argv) < 2:
        print("Usage: nmem_recall.py <query> [--unit-type TYPE] [--include-graph] [--no-wm]")
        sys.exit(1)
    
    query = sys.argv[1]
    unit_type = None
    include_graph = False
    include_wm = True
    
    # 解析参数
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--unit-type' and i + 1 < len(sys.argv):
            unit_type = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--include-graph':
            include_graph = True
            i += 1
        elif sys.argv[i] == '--no-wm':
            include_wm = False
            i += 1
        else:
            i += 1
    
    # 执行召回
    recall = NmemRecall()
    result = recall.recall(query, include_wm=include_wm, include_graph=include_graph, unit_type=unit_type)
    
    # 输出格式化结果
    prompt_content = recall.format_for_prompt(result)
    print(prompt_content)
    print(f"\n[Stats] Total tokens: ~{result.total_tokens}", file=sys.stderr)


if __name__ == '__main__':
    main()
