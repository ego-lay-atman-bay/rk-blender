# rk-blender
 Blender addon for importing .rk files

# Building
In order to build this library, you need to install

```
pip install blender-extension-builder
```

or

```
pip install -r requirements.txt
```

And then run

```
build-blender-extension
```

This is just my custom made extension builder that handles gathering the wheels for me (especially since the dependencies can update, and I don't want to manually gather those).

After you build the extension, just install it into blender.

```
blender --command extension install-file dist/rk_format-1.0.0.zip --repo user_default
```

Then in blender, go into preferences, add-ons, then enable "RK Format".

When you want to update the extension, just build it and install it again. However the dependencies won't be updated. In order to update the dependencies, just disable the add-on, close blender, open blender, then enable the add-on.
