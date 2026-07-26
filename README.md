# rk-blender
 Blender addon for importing .rk files

# Installation
Before installing, you have to build the extension.

## Setup

Before running any command, you need to have a both Blender and Python installed.

**Requirements**
- The latest version of [Blender](https://blender.org/download/). Make sure the Blender executable is on the PATH (so you can type `blender` into the command line to start it).
- [UV](https://docs.astral.sh/uv/) or [Python](https://python.org/download/) 3.13 (uv is easier).


You then need to install the extension builder program with


```shell
uv tool install blender-extension-builder --python 3.13
```

or if you're not using uv

```shell
pip install blender-extension-builder
```

If you get an error about `pip` not being a command, add `py -m` or `python -m` before the command.

## Building
First you need to download the repo. Either download the source code as zip and extract it, or run

```shell
git clone https://github.com/ego-lay-atman-bay/rk-blender/
cd rk-blender
```

Go into the project folder and enter the terminal (if you ran the above commands, you're already in it)

```shell
bbext -I -e
# or
bbext --install --enable
```

If you're running blender 4.2.4 LTS or 4.3.0, you need to add the `--ensure-cp311` flag to the command. This just fixes an issue with compatibility checks that this extension was effected by (though that issue is fixed in blender 4.3.1).

If you get a warning saying that blender is using a different python version, then uninstall blender-extension-builder (`uv tool uninstall blender-extension-builder`) and reinstall it changing the `--python` version to whatever the message says.

This is just my custom made extension builder that handles gathering the wheels for me (especially since the dependencies can update, and I don't want to manually gather those).

This should build and install the extension. If you don't want to install with the same command, you can either run this command, or install the resulting zip file (in the new `dist` folder) through the gui (by dragging and dropping the zip file into blender).

```shell
blender --command extension install-file dist/rk_format-1.0.0.zip --repo user_default
```

Open Blender, and go into preferences, add-ons, then enable "RK Format" (it may already be installed).


If you want to build the extension for all platforms (such as distributing or something), then just run this command.

```shell
bbext -a --split-platforms
```

## Using

To load a `.rk` file, just drag and drop it into blender. You can also load a `.rk` file by going to **file > Import > Import RK file**.

Just as a note, there is an option to load `.anim` files, however that's not finished, so it's disabled unless you have "Developer extras" enabled.

## Updating
When you want to update the extension, just build it and install it again. However the dependencies won't be updated automatically. In order to update the dependencies, just disable the add-on, close Blender, open Blender, then enable the add-on.
