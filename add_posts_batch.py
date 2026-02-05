#!/usr/bin/env python3
import subprocess
import os
import sys
import time

def run_cmd(cmd):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    else:
        print(f"Success")
    return result

# First, commit config files
print("=== Committing config files ===")
run_cmd("git add major_news_config.py monitor_international.py significance_filter.py")
run_cmd("git add data_international/monitor_state.json")
result = run_cmd("git commit -m 'Update configs and monitor state for breaking news'")
if result.returncode != 0:
    print("Config commit failed, continuing anyway")

# Get list of untracked post files
print("\n=== Finding untracked post files ===")
result = run_cmd("git ls-files --others --exclude-standard _posts/*.md | head -100")
if result.returncode == 0 and result.stdout.strip():
    untracked_count = len(result.stdout.strip().split('\n'))
    print(f"Found at least {untracked_count} untracked files (sampled)")
else:
    # Try alternative method
    result = run_cmd("find _posts -name '*.md' -type f | wc -l")
    total_files = int(result.stdout.strip()) if result.returncode == 0 else 0
    tracked_result = run_cmd("git ls-files _posts/*.md | wc -l")
    tracked_files = int(tracked_result.stdout.strip()) if tracked_result.returncode == 0 else 0
    untracked_count = total_files - tracked_files
    print(f"Total files: {total_files}, Tracked: {tracked_files}, Untracked: {untracked_count}")

if untracked_count > 0:
    print(f"\n=== Adding {untracked_count} untracked posts in batches ===")
    batch_size = 2000
    added = 0
    
    # Method 1: Use git add with directory (git handles internally)
    print("Method 1: git add _posts (git internal handling)")
    result = run_cmd("git add _posts")
    if result.returncode == 0:
        print("Successfully added all posts using git add _posts")
        added = untracked_count
    else:
        print("git add _posts failed, trying batch method")
        # Method 2: Batch using find and xargs with -n limit
        print("Method 2: Using find + xargs with batch size")
        cmd = f"find _posts -name '*.md' -type f -print0 | xargs -0 -n {batch_size} git add"
        result = run_cmd(cmd)
        if result.returncode == 0:
            print("Batch add successful")
            added = untracked_count
        else:
            print("Batch add also failed, trying git add --all")
            result = run_cmd("git add --all")
            if result.returncode == 0:
                print("git add --all succeeded")
                added = untracked_count
    
    if added > 0:
        print(f"\n=== Committing {added} posts ===")
        # Try to commit with a descriptive message
        commit_msg = f"Add {added} historical SEC EDGAR filings and USGS earthquakes (2020-2025)"
        result = run_cmd(f"git commit -m '{commit_msg}'")
        if result.returncode != 0:
            print("Commit failed, trying with --allow-empty")
            result = run_cmd(f"git commit --allow-empty -m '{commit_msg}'")
        
        if result.returncode == 0:
            print("Successfully committed posts")
            # Try to push
            print("\n=== Pushing to remote ===")
            result = run_cmd("git push origin main")
            if result.returncode != 0:
                print("Push failed, but commit is local")
        else:
            print("Commit failed completely")
else:
    print("No untracked posts found")

print("\n=== Final status ===")
run_cmd("git status --short | head -20")
