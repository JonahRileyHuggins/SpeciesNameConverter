#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
script name: petab_yamlpy
date: 11 -07 -2025
Author: Jonah R. Huggins

Description: shared-utility functions for Experiments class.

"""
# -----------------------Package Import & Defined Arguements-------------------#

@staticmethod 
def parse_kwargs(arg_list: list)-> dict:
    """Parses catchall function."""


    kwargs = {}


    for arg in arg_list:
        if '=' not in arg:
            raise ValueError(f"Invalid argument format: {arg}. Use key=value.")
        else:
            key, value = arg.split('=', 1)
            kwargs[key] = value


    return kwargs

