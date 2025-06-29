# setup.py

from cx_Freeze import setup, Executable

build_exe_options = {
    "packages": [
        "os",
        "uvicorn",
        "fastapi",
        "starlette",
        "sqlalchemy",
        "app"
    ],
    "includes": [
        "sqlalchemy.dialects.sqlite"
    ],
    "include_files": [
        ("dist", "dist"),
    ],
    "excludes": ["tkinter"],
}

setup(
    name="EduInsightAPI",
    version="1.0",
    description="由Hellohistory 开发的 EduInsight 分析系统",
    options={"build_exe": build_exe_options},
    executables=[
        Executable("main.py", base=None, target_name="edu_insight_server")
    ]
)
