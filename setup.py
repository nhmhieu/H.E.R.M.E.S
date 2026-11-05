from setuptools import setup

setup(
    name="hermes",
    version="1.0.0",
    py_modules=["ai_cli"], # Trỏ tới tên file code CLI của bạn (bỏ đuôi .py)
    install_requires=[
        "rich",
        "streamlit"
    ],
    entry_points={
        "console_scripts": [
            "hermes = ai_cli:main" # Chữ 'hermes' sẽ gọi hàm main() trong file ai_cli.py
        ]
    }
)