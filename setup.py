import sys
from cx_Freeze import setup, Executable

build_exe_options = {"include_files": ["icons"]}

setup(
    name="Zup",
    version="0.1",
    description="'Zup for JIRA",
    options={"build_exe": build_exe_options},
    executables=[Executable("zup/zup.py")],
)
