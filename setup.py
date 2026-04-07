from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cronwatch",
    version="0.1.0",
    author="cronwatch contributors",
    description="A lightweight CLI tool to monitor, log, and alert on cron job failures",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/cronwatch",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.8",
    install_requires=[
        "pyyaml>=6.0",
        "requests>=2.28.0",
        "slack-sdk>=3.19.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=23.0",
            "flake8>=6.0",
            "mypy>=1.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "cronwatch=cronwatch.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: System :: Monitoring",
        "Topic :: System :: Systems Administration",
    ],
    keywords="cron monitoring alerting slack email devops",
)
