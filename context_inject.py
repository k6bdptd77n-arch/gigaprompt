#!/usr/bin/env python3
"""
Context Injector — Inject memory into ANY AI prompt
==================================================
Usage:
  cat file.py | context_inject.py --prefix "Review this code"
  context_inject.py --prompt "Help me with auth"
  
Works with:
  - Claude Code
  - OpenAI Codex
  - OpenClaw
  - Any CLI agent
"""

import sys
import argparse
import requests
import os

DEFAULT_API = os.environ.get('SUPER_MEMORY_API', 'http://127.0.0.1:8080')


def get_context(api_url: str, limit: int = 10) -> str:
    """Get memory context from API."""
    try:
        resp = requests.get(f'{api_url}/context', timeout=2)
        if resp.status_code == 200:
            return resp.json().get('context', '')
        return ''
    except:
        return ''


def get_summary(api_url: str) -> str:
    """Get memory summary."""
    try:
        resp = requests.get(f'{api_url}/summary', timeout=2)
        if resp.status_code == 200:
            data = resp.json()
            return f"""Memory: {data.get('total', 0)} entries
  ✅ Completed: {data.get('completed', 0)}
  ⚖️ Decisions: {data.get('decisions', 0)}
  🚧 Blockers: {data.get('blockers', 0)}"""
        return ''
    except:
        return ''


def inject(prompt: str, prefix: str = None, suffix: str = None, 
            api_url: str = None, include_summary: bool = False) -> str:
    """
    Inject memory context into prompt.
    
    Returns enhanced prompt with memory context.
    """
    api_url = api_url or DEFAULT_API
    
    parts = []
    
    # Prefix
    if prefix:
        parts.append(prefix)
    
    # Memory context
    context = get_context(api_url)
    if context:
        if prefix:
            parts.append(f"\n\n{context}")
        else:
            parts.append(context)
    
    # Original prompt
    parts.append(prompt)
    
    # Summary (optional)
    if include_summary:
        summary = get_summary(api_url)
        if summary:
            parts.append(f"\n\n## Memory Summary\n{summary}")
    
    # Suffix
    if suffix:
        parts.append(f"\n\n{suffix}")
    
    return '\n'.join(parts)


def main():
    parser = argparse.ArgumentParser(
        description='Inject memory context into AI prompts'
    )
    parser.add_argument('prompt', nargs='?', help='Prompt text')
    parser.add_argument('--prefix', '-p', help='Text before context')
    parser.add_argument('--suffix', '-s', help='Text after context')
    parser.add_argument('--api', '-a', default=DEFAULT_API, help='Memory API URL')
    parser.add_argument('--summary', action='store_true', help='Include summary')
    parser.add_argument('--file', '-f', help='Read prompt from file')
    parser.add_argument('--stdin', action='store_true', help='Read from stdin')
    parser.add_argument('--check', action='store_true', help='Check API status')
    
    args = parser.parse_args()
    
    # Check API status
    if args.check:
        try:
            resp = requests.get(f'{args.api}/health', timeout=2)
            if resp.status_code == 200:
                print(f"✅ Memory agent running at {args.api}")
                summary = get_summary(args.api)
                if summary:
                    print(f"\n{summary}")
            else:
                print(f"❌ Memory agent returned {resp.status_code}")
                sys.exit(1)
        except Exception as e:
            print(f"❌ Cannot connect to memory agent at {args.api}")
            print(f"   Start with: python3 ~/.super_memory/memory_agent.py &")
            sys.exit(1)
        sys.exit(0)
    
    # Read prompt
    prompt = ''
    
    if args.stdin:
        prompt = sys.stdin.read()
    elif args.file:
        with open(args.file, 'r') as f:
            prompt = f.read()
    elif args.prompt:
        prompt = args.prompt
    else:
        # No prompt, just show context
        context = get_context(args.api)
        if context:
            print(context)
        else:
            print("No context available (or memory agent not running)")
        sys.exit(0)
    
    # Inject context
    result = inject(
        prompt=prompt,
        prefix=args.prefix,
        suffix=args.suffix,
        api_url=args.api,
        include_summary=args.summary
    )
    
    print(result)


if __name__ == '__main__':
    main()
