"""Turning a structure file into a Bedrock resource pack.

Everything here is a piece of the pipeline `scaffold_core` drives: reading the
`.mcstructure`, resolving each block to cubes and textures, and writing the
entity, animation, render controller and manifest files the pack is made of.

Nothing in here knows about a window.
"""
