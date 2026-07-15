#!/usr/bin/env python3
"""Backward-compatible wrapper. Prefer backup_existing_data.py """
import sys
from pathlib import Path

# Re-run as full backup or products-only via new script
args = ['--collection', 'products']
if '--file' in sys.argv:
    i = sys.argv.index('--file')
    args += ['--file', sys.argv[i + 1]]

print('Note: use backup_existing_data.py for all collections.')
print('Running products backup...\n')

import runpy
sys.argv = [str(Path(__file__).with_name('backup_existing_data.py'))] + args
runpy.run_path(str(Path(__file__).with_name('backup_existing_data.py')), run_name='__main__')
