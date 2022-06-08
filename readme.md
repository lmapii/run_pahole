
- [Pre-Requisites](#pre-requisites)
- [Scope](#scope)
- [Usage](#usage)
  - [Adding files](#adding-files)
  - [Ignores](#ignores)
- [Execution options](#execution-options)
  - [Lazy evaluation](#lazy-evaluation)
- [Tool output](#tool-output)
- [Pitfalls and tips](#pitfalls-and-tips)
  - [Invalid dwarf data](#invalid-dwarf-data)

# Pre-Requisites

* This is a wrapper for [`pahole`](https://linux.die.net/man/1/pahole), which only runs on linux. Make sure that `pahole` is installed and in your `$PATH`.
* Install `python >= 3.6.0` aswell as `pip`, it is typically pre-installed on your machine
* Install all required packages:

```bash
pip install -r path/to/tttpytilities/integrity/requirements.txt
```

> **Remark:** You can also run this tool in `docker`, check the provided [`Dockerfile`](Dockerfile). The provided [`makefile`](makefile) contains two targets that you can use to create the image and attach to a running container.

# Scope

This wrapper parses the output of `pahole` to determine whether structures can be optimized (see also [The lost art of struct padding](http://www.catb.org/esr/structure-packing/) and [this article](https://interrupt.memfault.com/blog/c-struct-padding-initialization?query=struct) on the Interrupt blog.)

This is not a *all-usecases-considered* tool and it will probably never be. It might work for your usecase or it won't. Feel free to play around with the implementation and adapt it to your needs. This is also the reason why there's no installation script: The script is intended to be run directly from the command line using `python`. Future versions of this (currently unversioned) script might create a proper `python` module and/or `docker` setup.

# Usage

All this wrapper needs is a configuration file which contains your project setup. Thus invoking the script is as easy as:

```bash
python /path/to/run_pahole.py /path/to/your-config.json
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

Each entry is another object with two properties `source` and `blacklist`, where only `source` is a **required** list of paths in glob-style (resolved by `python`'s [pathlib](https://docs.python.org/3/library/pathlib.html)). Th

The script supports a list of files to be used as blacklist: Every filename from the list of files determined via the `source` field is matched against this list of names. Should the filename match then the file is excluded (these are plain filenames and not globs). In the above example *SomeObject.o" would be ignored.

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
