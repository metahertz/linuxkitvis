#LinuxKitVis
## Visualising LinuxKit Mounts, Binds and File inheritance.

###Use
```
graphit.py -i <yourlinuxkityml> -o <graphname>
```

### Output
Output is an SVG diagram showing:

- All Images (by name, image and tag) in the configuration.
- Colourcoding for init, onboot and service images.
- Mounts for onboot and service images.
- Source and dest information for each mount.
- Information on each mount (rbind etc).

An example is here: [](./img/example.svg)

### Dependancies.

Graphviz and associated tools will need to be installed on your system. for me:

``` 
brew install graphviz
```

You'll also need docker installed on the system and have the `docker` command in your path. we call out to it to inspect the LinuxKit images.

Needed Python3 dependancies are in `requirements.txt`

```
pip3 install -r requirements.txt
```

###Why
Working with LinuxKit now for a few weeks, debugging issues I found was a lot easier with a "map" of the system. This is a *Very Hacky* attempt at automating that.

### Improvements Needed!

#### Overrides
This only visualizes binds from the `LABEL` metadata in each image's dockerfile (org.mobyproject.config). I know these are often overridden in the linuxkit yaml files, so we need to also read these in and display them.

I'm stll not 100% sure which ones "win" or how they are merged when both the `LABEL` and the yaml have binds.

#### Files
The files section adds things to the "RootFS" just like images in init, i'll be adding these to the diagram next.

#### Tidyness
This is my first time playing with GraphViz and it shows. Making this tidier with more readable line labels and spacing would be awesome!

#### Docker API
I'm currently calling out to `docker inspect` (and `docker pull` to have an image to inspect). This is nasty, however the pyDocker client doesnt seem to support inspect actions on anything other than running containers. I didn't have time to look into this.


