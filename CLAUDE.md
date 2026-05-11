# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
This file is human-written, NOT to be edited by the Claude agent.

## GUIDELINES

These are key guidelines for creating and modifying code

1. All project- and code-related documentation and structural information should be put in CONCEPT.md
   1. This file is created and edited by Claude to document the high-level structure of the project
   2. This file needs to be kept up to date, i.e., changed when code changes demand it
   3. This file is to be used by Claude as a first source of information about the code, to avoid needless file reading
   4. Each package and folder contains its own file, i.e., the repository consist of a hierarchy of CONCEPT.md files
   5. Each CONCEPT.md file contains information and level od detail appropriate to its level in the hierarchy
2. All code should be documented well, when created and when modified
   1. Classes and methods should have explanations of their purpose
   2. In-line comments should be put where necessary to explain more complicated segments
3. Python type annotation should be used throughout the code
