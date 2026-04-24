from setuptools import setup, find_packages

setup(
    name="oid-framework",
    version="0.1.0",
    author="Yann Abadie",
    description="Operational Integrity Dynamics for Autonomous AI Agents",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "networkx>=3.0",
        "matplotlib>=3.5",
        "numpy>=1.21",
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
