import sys

with open('monitor_international_enhanced.py', 'r') as f:
    lines = f.readlines()

# Find the __init__ method and add enable_git_commit
for i, line in enumerate(lines):
    if 'def __init__' in line:
        # Find the line after self.state = self.default_state()
        for j in range(i, min(i+30, len(lines))):
            if 'self.state = self.default_state()' in lines[j]:
                # Insert after this line
                indent = len(lines[j]) - len(lines[j].lstrip())
                lines.insert(j+1, ' ' * indent + 'self.enable_git_commit = True\n')
                break
        break

# Find where to insert git_commit_and_push method (before publish_story)
for i, line in enumerate(lines):
    if 'def publish_story' in line:
        # Insert before this line
        indent = len(line) - len(line.lstrip())
        git_method = '''
    def git_commit_and_push(self, filenames):
        """Add files, commit with timestamped message, and push to origin/main."""
        import subprocess
        from datetime import datetime
        from pathlib import Path
        
        if not filenames:
            logger.warning("No filenames provided for git commit; skipping.")
            return False
        
        if not self.enable_git_commit:
            logger.info("Git commit/push disabled; skipping.")
            return True
        
        repo_root = Path(__file__).resolve().parent
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
        commit_msg = f"Auto-publish {{len(filenames)}} international stories at {timestamp}"
        
        try:
            add_result = subprocess.run(
                ["git", "add", *filenames],
                cwd=repo_root,
                capture_output=True,
                text=True
            )
            if add_result.returncode != 0:
                logger.error(f"Git add failed: {{add_result.stderr.strip() or add_result.stdout.strip()}}")
                return False
            
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=repo_root,
                capture_output=True,
                text=True
            )
            if commit_result.returncode != 0:
                logger.error(f"Git commit failed: {{commit_result.stderr.strip() or commit_result.stdout.strip()}}")
                return False
            
            push_result = subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=repo_root,
                capture_output=True,
                text=True
            )
            if push_result.returncode != 0:
                logger.error(f"Git push failed: {{push_result.stderr.strip() or push_result.stdout.strip()}}")
                return False
            
            logger.info("Git commit and push completed successfully.")
            return True
        except Exception as e:
            logger.error(f"Error during git commit/push: {{e}}")
            return False
'''.replace('\n', '\n' + ' ' * indent)
        lines.insert(i, git_method)
        break

# Modify publish_story to call git_commit_and_push
for i, line in enumerate(lines):
    if 'def publish_story' in line:
        # Find the return True line in publish_story
        for j in range(i, min(i+50, len(lines))):
            if 'return True' in lines[j] and 'def ' not in lines[j]:
                # Insert before return True
                indent = len(lines[j]) - len(lines[j].lstrip())
                lines.insert(j, ' ' * indent + '            # Git commit and push\n')
                lines.insert(j+1, ' ' * indent + '            self.git_commit_and_push([filename])\n')
                break
        break

# Write back
with open('monitor_international_enhanced_git.py', 'w') as f:
    f.writelines(lines)

print("Modified file saved as monitor_international_enhanced_git.py")
