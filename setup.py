# -*- coding: utf-8 -*-
"""
setup.py for pysollya — self-contained Python bindings for Sollya 8.0.

This build script compiles the Sollya C/C++ library sources directly into
the Python extension module, so no pre-installed libsollya is needed.
GMP, MPFR, MPFI, fplll and libxml2 are still required as system/local deps.

Configure dependency paths via environment variables:
    GMP_DIR, MPFR_DIR, MPFI_DIR  — install prefixes (include/ and lib/ subdirs)
    FPLLL_DIR                    — fplll install prefix
    XML2_DIR                     — libxml2 install prefix

Or set them all at once with:
    SOLLYA_DEP_DIR               — common prefix for all dependencies
"""

import os
import subprocess
import sys
import sysconfig
from pathlib import Path

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext as _build_ext

# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------
SOLLYA_SRC = Path(__file__).resolve().parent / "sollya-8.0"

def _dep_dir():
    return os.environ.get("SOLLYA_DEP_DIR") or None

def _get_dirs(name):
    """Return (include_dirs, library_dirs) for a dependency.

    If neither the specific env var (e.g. GMP_DIR) nor SOLLYA_DEP_DIR is set,
    returns empty lists so the compiler uses default system search paths.
    """
    env_key = f"{name.upper()}_DIR"
    base = os.environ.get(env_key) or _dep_dir()
    if base is None:
        return [], []
    inc = os.path.join(base, "include")
    lib = os.path.join(base, "lib")
    dirs_inc, dirs_lib = [], []
    if os.path.isdir(inc):
        dirs_inc.append(inc)
    if os.path.isdir(lib):
        dirs_lib.append(lib)
    return dirs_inc, dirs_lib


# ---------------------------------------------------------------------------
# Collect Sollya C/C++ source files (matches Makefile.am libsollya_la_SOURCES)
# ---------------------------------------------------------------------------
SOLLYA_C_SOURCES = [
    "mpfi-compat.c",
    "hash.c",
    "hooks.c",
    "polynomials.c",
    "sollya-library-wrappers.c",
    "sollya-messaging.c",
    "bitfields.c",
    "printf.c",
    # Pre-generated parser/lexer files (no flex/bison needed)
    "internparser.c",
    "miniparser.c",
    "parser.c",
    "internlexer.c",
    "lexer.c",
    "minilexer.c",
    # Core sources
    "assignment.c",
    "autodiff.c",
    "base-functions.c",
    "chain.c",
    "double.c",
    "execute.c",
    "expression.c",
    "external.c",
    "general.c",
    "signalhandling.c",
    "implement.c",
    "implementconst.c",
    "infnorm.c",
    "integral.c",
    "library.c",
    "plot.c",
    "proof.c",
    "fpminimax.c",
    "remez.c",
    "match.c",
    "taylorform.c",
    "chebyshevform.c",
    "chebyshevformaux.c",
    "sollya-help.c",
    "supnorm.c",
    "sturm.c",
    "taylor.c",
    "worstcase.c",
    "xml.c",
]

SOLLYA_CXX_SOURCES = [
    "fplll_wrapper.cpp",
]


# ---------------------------------------------------------------------------
# Gather include / library directories
# ---------------------------------------------------------------------------
include_dirs = ["sollya-8.0"]  # for sollya.h, config.h
library_dirs = []
extra_link_args = []

for dep in ("gmp", "mpfr", "mpfi", "fplll"):
    inc, lib = _get_dirs(dep)
    include_dirs.extend(inc)
    library_dirs.extend(lib)

# libxml2: try xml2-config, then pkg-config, then manual
xml2_dir = os.environ.get("XML2_DIR", "")
if xml2_dir:
    include_dirs.append(os.path.join(xml2_dir, "include"))
    include_dirs.append(os.path.join(xml2_dir, "include", "libxml2"))
    library_dirs.append(os.path.join(xml2_dir, "lib"))
else:
    # Try xml2-config
    try:
        xml2_cflags = subprocess.check_output(
            ["xml2-config", "--cflags"], stderr=subprocess.DEVNULL
        ).decode().strip().split()
        for f in xml2_cflags:
            if f.startswith("-I"):
                include_dirs.append(f[2:])
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Try pkg-config
        try:
            xml2_cflags = subprocess.check_output(
                ["pkg-config", "--cflags", "libxml-2.0"], stderr=subprocess.DEVNULL
            ).decode().strip().split()
            for f in xml2_cflags:
                if f.startswith("-I"):
                    include_dirs.append(f[2:])
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback: macOS SDK
            sdk_xml2 = "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/usr/include/libxml2"
            if os.path.isdir(sdk_xml2):
                include_dirs.append(sdk_xml2)

# Libraries to link
libraries = ["gmp", "mpfr", "mpfi", "fplll", "xml2", "m", "z"]

# macOS: add -lstdc++ for fplll C++ support
if sys.platform == "darwin":
    libraries.append("stdc++")
    # Add rpath for the dependency libs
    for ld in library_dirs:
        extra_link_args.extend(["-Wl,-rpath," + ld])

# ---------------------------------------------------------------------------
# Build the list of C/C++ source file paths (relative to setup.py dir)
# ---------------------------------------------------------------------------
c_source_paths = [os.path.join("sollya-8.0", f) for f in SOLLYA_C_SOURCES]
cxx_source_paths = [os.path.join("sollya-8.0", f) for f in SOLLYA_CXX_SOURCES]

# ---------------------------------------------------------------------------
# Compile flags
# ---------------------------------------------------------------------------
extra_compile_args_c = ["-fPIC", "-std=c99", "-w"]  # -w suppresses warnings in sollya code
extra_compile_args_cxx = ["-fPIC", "-std=c++11", "-w"]

# We need to define HAVE_CONFIG_H so sollya sources pick up config.h
define_macros = [("HAVE_CONFIG_H", "1")]


# ---------------------------------------------------------------------------
# Custom build_ext that handles C vs C++ sources and runs Cython
# ---------------------------------------------------------------------------
class build_ext(_build_ext):
    """Custom build_ext that:
    1. Runs ./configure in the Sollya source tree (if needed)
    2. Runs Cython on .pyx files
    3. Compiles C sources with C flags and C++ sources with C++ flags
    """

    def _run_configure(self):
        """Run ./configure inside the Sollya source directory to generate config.h.

        Skipped if config.h already exists.  Dependency prefixes are forwarded
        via --with-gmp=, --with-mpfr=, etc. when available.
        """
        sollya_dir = SOLLYA_SRC
        config_h = sollya_dir / "config.h"
        if config_h.exists():
            print(f"setup.py: {config_h} already exists — skipping configure")
            return

        print(f"setup.py: running ./configure in {sollya_dir} …")

        # Build the configure command with dependency paths
        configure_cmd = ["./configure", "--disable-dependency-tracking"]

        dep_mapping = {
            "gmp":   "GMP_DIR",
            "mpfr":  "MPFR_DIR",
            "mpfi":  "MPFI_DIR",
            "fplll": "FPLLL_DIR",
        }
        dep_default = _dep_dir()
        for lib_name, env_key in dep_mapping.items():
            prefix = os.environ.get(env_key, dep_default)
            if prefix and os.path.isdir(prefix):
                configure_cmd.append(f"--with-{lib_name}={prefix}")

        # libxml2
        xml2_prefix = os.environ.get("XML2_DIR", dep_default)
        if xml2_prefix and os.path.isdir(xml2_prefix):
            configure_cmd.append(f"--with-xml2={xml2_prefix}")

        print(f"setup.py: {' '.join(configure_cmd)}")
        subprocess.check_call(configure_cmd, cwd=str(sollya_dir))

    def build_extensions(self):
        # Run ./configure in the Sollya source tree first
        self._run_configure()

        # Ensure Cython is available
        try:
            from Cython.Build import cythonize
        except ImportError:
            raise RuntimeError("Cython is required to build pysollya")

        # Cythonize .pyx → .c
        self.distribution.ext_modules[:] = cythonize(
            self.distribution.ext_modules,
            compiler_directives={"language_level": "3"},
        )

        # Customize the compiler for C++ files
        for ext in self.extensions:
            ext._cpp_sources = []
            new_sources = []
            for src in ext.sources:
                if src.endswith(".cpp"):
                    ext._cpp_sources.append(src)
                else:
                    new_sources.append(src)
            ext.sources = new_sources + ext._cpp_sources

        _build_ext.build_extensions(self)

    def build_extension(self, ext):
        # We need special handling: C files with -std=c99 and C++ with -std=c++11
        # The simplest approach: compile C++ sources separately, then link together

        # Save original sources
        original_sources = ext.sources[:]
        cpp_sources = getattr(ext, '_cpp_sources', [])

        if cpp_sources:
            # Compile C++ sources with C++ flags
            c_sources = [s for s in original_sources if not s.endswith('.cpp')]
            cpp_only = [s for s in original_sources if s.endswith('.cpp')]

            # First compile C sources (including cython output)
            ext.sources = c_sources
            ext.extra_compile_args = extra_compile_args_c
            c_objects = self.compiler.compile(
                c_sources,
                output_dir=self.build_temp,
                macros=ext.define_macros or [],
                include_dirs=ext.include_dirs,
                debug=self.debug,
                extra_postargs=extra_compile_args_c,
                depends=ext.depends,
            )

            # Then compile C++ sources
            cxx_objects = self.compiler.compile(
                cpp_only,
                output_dir=self.build_temp,
                macros=ext.define_macros or [],
                include_dirs=ext.include_dirs,
                debug=self.debug,
                extra_postargs=extra_compile_args_cxx,
                depends=ext.depends,
            )

            # Link everything together
            objects = c_objects + cxx_objects
            ext._built_objects = objects
            ext.sources = original_sources

            # Get the output filename
            ext_path = self.get_ext_fullpath(ext.name)
            os.makedirs(os.path.dirname(ext_path), exist_ok=True)

            # Link
            self.compiler.link_shared_object(
                objects,
                ext_path,
                libraries=self.get_libraries(ext),
                library_dirs=ext.library_dirs,
                runtime_library_dirs=ext.runtime_library_dirs,
                extra_postargs=ext.extra_link_args or [],
                export_symbols=self.get_export_symbols(ext),
                debug=self.debug,
                build_temp=self.build_temp,
                target_lang="c++",
            )
        else:
            ext.extra_compile_args = extra_compile_args_c
            _build_ext.build_extension(self, ext)


# ---------------------------------------------------------------------------
# Extension definition
# ---------------------------------------------------------------------------
pysollya_ext = Extension(
    "pysollya._pysollya",
    sources=(
        ["pysollya/_pysollya.pyx"]
        + c_source_paths
        + cxx_source_paths
    ),
    include_dirs=include_dirs,
    library_dirs=library_dirs,
    libraries=libraries,
    define_macros=define_macros,
    extra_compile_args=extra_compile_args_c,
    extra_link_args=extra_link_args,
    language="c",  # primary language; C++ handled by custom build_ext
)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
setup(
    name="pysollya",
    version="0.1.2",
    description="Self-contained Python wrapper for the Sollya library",
    packages=["pysollya"],
    ext_modules=[pysollya_ext],
    cmdclass={"build_ext": build_ext},
    setup_requires=["cython>=0.29"],
    install_requires=[],
    python_requires=">=3.8",
)
