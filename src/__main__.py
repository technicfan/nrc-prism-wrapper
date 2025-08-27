#!/usr/bin/env python3

# __main__.py
import os
import sys

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import and run your main application
from wrapper import main

if __name__ == "__main__":
    main()