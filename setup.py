"""
JackpotChain 패키지 설정
"""

from setuptools import setup, find_packages

setup(
    name="jackpotchain",
    version="0.1.0",
    description="가챠 시스템이 내장된 블록체인",
    author="JackpotChain Team",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "aiohttp>=3.9.0",
        "ecdsa>=0.19.0",
        "textual>=0.50.0",
        "rich>=13.0.0",
        "cryptography>=42.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.0",
            "pyinstaller>=6.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "jackpotchain=jackpotchain.cli.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
