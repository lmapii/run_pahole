
- [Scope](#scope)
- [Pre-Requisites](#pre-requisites)
  - [Local installation](#local-installation)
  - [Building the provided container](#building-the-provided-container)
- [Usage](#usage)
  - [Adding files](#adding-files)
  - [Ignores](#ignores)
- [Execution options](#execution-options)
  - [Lazy evaluation](#lazy-evaluation)
- [Tool output](#tool-output)
- [Pitfalls and tips](#pitfalls-and-tips)
  - [Invalid dwarf data](#invalid-dwarf-data)


# Scope

This wrapper parses the output of `pahole` to determine whether structures can be optimized (see also [The lost art of struct padding](http://www.catb.org/esr/structure-packing/) and [this article](https://interrupt.memfault.com/blog/c-struct-padding-initialization?query=struct) on the Interrupt blog.)


# Pre-Requisites

This is a wrapper for [`pahole`](https://linux.die.net/man/1/pahole), which only runs on Linux. If you're running or installing `run_pahole` locally, make sure that `pahole` is installed and in your `$PATH`. Alternatively, you can use the provided `docker` setup to run the tool in a container, where `pahole` is already available.

## Local installation

To install `run_pahole` locally, install `python >= 3.6.0` with `pip` and use a virtual environment to install `run_pahole`:

```bash
$ pipenv --rm
$ mkdir .venv
$ pipenv install --dev
$ pipenv shell
$ pipenv install -e .
```

## Building the provided container

The provided [`makefile`](makefile) contains the target `docker-build` to create the `run_pahole:latest` image using the [`Dockerfile`](Dockerfile) in the repository root. Assuming you have `make` installed, you can simply run:

```bash
$ make docker-build
```

Otherwise, use the command provided in the `makefile` target.


# Usage

All this wrapper needs is a configuration file which contains your project setup. You can invoke the script locally as follows:

```bash
run_pahole /path/to/your-config.json
```

`run_pahole` is available after you install it in your virtual environment, or within the Docker image. A commodity target `docker-run` is available in the provided [`makefile`](makefile), which executes `docker run` for the given `ARG`:

```bash
make docker-run ARGS=/path/to/your-config.json
```

The main ingredient to the script is the configuration file, which uses the `.json` format. Let's use the following example as reference:

```json
{
    "paths": [
        {
            "source" ["../path/to/build/output/*.o"],
            "blacklist": ["SomeObject.o"]
        }
    ],
    "ignore": ["(struct ){0,1}[\\w\\s]*_.*", "(struct ){0,1}TcpIp*"]
}
```

> Heads-Up: **All paths must be specified relative to the configuration file**. No other path-dependencies need to be considered, the script should resolve all of them properly. Please also check the [`Dockerfile`](Dockerfile) and/or example invocation of `docker run` within the [`makefile`](makefile).

Please check the `jsonschema` within the [python script](run_pahole.py) itself for a complete reference.

## Adding files

The script uses a list of path as input for objects, any path is configured via the **required** field `paths`:

```json
{
    "paths": [
        {
            "source" ["../path/to/build/output/*.o"],
            "blacklist": ["SomeObject.o"]
        }
    ],
    ...
}
```

Each entry is another object with two properties `source` and `blacklist`, where only `source` is a **required** list of paths in glob-style (resolved by `python`'s [pathlib](https://docs.python.org/3/library/pathlib.html)).

The script supports a list of files to be used as blacklist: Every filename from the list of files determined via the `source` field is matched against this list of names. Should the filename match then the file is excluded (these are plain filenames and not globs). In the above example "SomeObject.o" would be ignored.

## Ignores

The optional property `ignores` can be used to define a list of regular expressions that will be used on each structure that has been found by `pahole`:

```json
{
    ...
    "ignore": ["(struct ){0,1}[\\w\\s]*_.*", "(struct ){0,1}TcpIp*"]
}
```

In the above example any structure that starts with `TcpIp` or any structure with a single underscore will be ignored by the script. This list can be extended, e.g., for vendor objects that cannot be modified or re-packed.


# Execution options

## Lazy evaluation

A lazy execution (using the `--lazy` option) will execute `pahole` with the `--packable` argument to identify elements whose size can be decreased when re-packing. If `--lazy` is not set, the tool will look for *"try to pack"* annotations in the execution of `pahole` instead, requiring re-ordering of members even if it doesn't lead to smaller object sizes.

> **Remark:** The resolved names can be different, e.g., for structures that do not use a `typedef`, in case a lazy execution is chosen. This should not stop you from using the tool. Simply extend your regular expressions for `(struct ){0,1}`.


# Tool output

In case any problems have been found, the tool will list the elements with problems at the end of the execution. Since the output of `pahole` is quite verbose, two dump files will be created in case of issues for further analysis:

* `[json-basename]_dump_all.h` contains **all** relevant elements that could be extracted
* `[json-basename]_dump_packable.h` contains all elements that need to be re-packed (including the full `pahole` output).


# Pitfalls and tips

## Invalid dwarf data

If your objects contain invalid or corrupt `DWARF` data it may happen that `pahole` is not able to extract any information (the execution will fail completely, please exclude such objects) or it might be able to resolve the structure of the code but provide invalid names, e.g., the following might happen:

```c++
// E.g., the following structure
typedef struct {
    uint16_t realName;
    uint16_t anotherName;
} SomeDataType;

// could be listed as following for `pahole -a -A some/obj.o`
typedef struct {
    uint16_t randomName;
    uint16 randomName;
} SomeDataType;
```

Typically `pahole` is quite robust and the members themselves will have the correct type, but it might not provide the correct names. Use `llvm-dwarfdump` to verify the content of your objects (`llvm-dwarfdump` comes pre-installed in the provided [`Dockerfile`](Dockerfile)).
