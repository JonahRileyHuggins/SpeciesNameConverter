#!/bin/env python3 
"""
filename: file_loader.py
author: Jonah R. Huggins
Created On: 2025-04-18

description: loads a file. 
"""

import os
import json
from types import SimpleNamespace

import yaml
import pandas as pd


class FileLoader:
    """Generic Object for loading everything listed in a YAML config."""
    def __init__(self, config_path: str | os.PathLike):
        self.config_path = config_path

        # 1) load the raw YAML into a DotDict
        self.config = Config.file_loader(self.config_path)
        
        self.problems = []
        self.parameter_file = None

    def _petab_files(self) -> SimpleNamespace:
        """Loads petab files for an experiment into memory"""
        yaml_dir = os.path.dirname(self.config_path)

        # 2) load the parameter file
        param_fp = os.path.join(yaml_dir, self.config.parameter_file)
        self.parameter_file = pd.read_csv(param_fp, sep="\t")

        # 3) load each problem’s files into a list of namespaces
        for problem in self.config.problems:

            p = SimpleNamespace()
            p.cell_count = problem.cell_count

            for attr in ("condition_files", "measurement_files", "observable_files", "sbml_files", "visualization_df"):

                file_list = getattr(problem, attr, None)

                if file_list is None:
                    continue

                loaded = []
                for rel in file_list:
                    fp = os.path.join(yaml_dir, rel)
                    ext = os.path.splitext(fp)[1].lower()

                    #SBML files only need path, loaded into SingleCell
                    if ext in (".sbml", ".xml"):
                        
                        loaded.append(fp)
                    else:
                        # CSV/TSV → DataFrame
                        loaded.append(pd.read_csv(fp, sep="\t"))
                setattr(p, attr, loaded)
            self.problems.append(p)

        # 4) clean up
        del self.config_path

    def _extract_model_build_files(self) -> SimpleNamespace:
        """returns input files as pandas dataframes, contained in an object for easy reference."""

        model_files = SimpleNamespace()

        yaml_dir = os.path.dirname(self.config_path)

        data_dir = os.path.join(yaml_dir, self.config.compilation.directory)

        for key, value in self.config.compilation.files.items():

            file_path = os.path.join(data_dir, value)

            setattr(model_files, key, pd.read_csv(file_path, sep = '\t', index_col=0, header=0))

        return model_files
    

class Config:

    @staticmethod
    def file_loader(file_path: os.PathLike, **kwargs):
        """Dynamic File loader based on extension"""

        ext = os.path.splitext(file_path)[1].lower()

        loader_class = {
            '.yml': YAML, 
            '.yaml': YAML, 
            '.json': JSON, 
            '.csv': CSV, 
            '.tsv': CSV, 
            '.txt': CSV,
        }.get(ext)

        if loader_class is None:
            raise ValueError(f"Unsupported file type: {ext}")

        file_instance = loader_class(file_path)

        try:
            return file_instance.loader(**kwargs)

        except TypeError:
            return file_instance.loader()


class File:

    def __init__(self, file_path: os.PathLike):
        self.file_path = file_path

    def loader(self):
        """parent loader function"""
        raise NotImplementedError("Subclasses must implement this method")
    
class YAML(File):

    def __init__(self, file_path):
        super().__init__(file_path)

    def loader(self):
        """Load yaml file"""
        try:
            with open(self.file_path, encoding='utf-8', mode='r') as file:
                config = yaml.safe_load(file)
                return DotDict(config)
        except FileNotFoundError:
            print(f"Error: File not found at path: {self.file_path}")
            return None
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file: {e}")
            return None

class JSON(File):

    def __init__(self, file_path):
        super().__init__(file_path)

    def loader(self):
        """Load JSON file"""
        try:
            with open(self.file_path, encoding='utf-8', mode='r') as file:
                config = json.load(file)
                return DotDict(config)
        except FileNotFoundError:
            print(f"Error: file not found at path: {self.file_path}")
            return None
        except json.JSONDecodeError as e:
            print(f" Error decoding JSON file: {e}")
            return None
        
class CSV(File):

    def __init__(self, file_path):
        super().__init__(file_path)

    def loader(self, **kwargs): 
        """Load CSV/TSV file"""
        kwargs.setdefault("sep", "\t")
        return pd.read_csv(filepath_or_buffer=self.file_path, engine = 'python', **kwargs)
    
class DotDict(dict):
    """Converts JSON and YAML files into dot notation rather than square brackets"""

    def __getattr__(self, attr): # called when you try to access a method that doesn't yet exist
        """Called when user tries to access an object not-yet-created, returns"""
        val = self.get(attr)

        if isinstance(val, dict): # if param is dict: convert to dot-notation
            return DotDict(val)
        
        elif isinstance(val, list): # if param is list: convert evey entry. 
            return [DotDict(x) if isinstance(x, dict) else x for x in val]
        
        return val
    
    __setattr__ = dict.__setitem__ 
    __delattr__ = dict.__delitem__
