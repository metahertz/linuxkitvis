#!/usr/bin/env python3

import sys, getopt
import graphviz as gv
import yaml
import json
import functools
import subprocess

###################################################
# Helper fucntions for graphviz
# from http://matthiaseisen.com/articles/graphviz/
###################################################
graph = functools.partial(gv.Graph, format='svg')
digraph = functools.partial(gv.Digraph, format='svg')
def add_nodes(graph, nodes):
    for n in nodes:
        if isinstance(n, tuple):
            graph.node(n[0], **n[1])
        else:
            graph.node(n)
    return graph

def add_edges(graph, edges):
    for e in edges:
        if isinstance(e[0], tuple):
            graph.edge(*e[0], **e[1])
        else:
            graph.edge(*e)
    return graph

def apply_styles(graph, styles):
    graph.graph_attr.update(
        ('graph' in styles and styles['graph']) or {}
    )
    graph.node_attr.update(
        ('nodes' in styles and styles['nodes']) or {}
    )
    graph.edge_attr.update(
        ('edges' in styles and styles['edges']) or {}
    )
    return graph

# End of Graphviz helpers.
###################################################

# Setup globals set in parselkyaml() and read elsewhere
kernels = {}
init = {}
onboot = {}
services = {}
files = {}

def main(argv):
   inputfile = ''
   outputfile = ''
   try:
      opts, args = getopt.getopt(argv,"hi:o:",["ifile=","ofile="])
   except getopt.GetoptError:
      print ('graphit -i <Linuxkit yml> -o <Diagram SVG>')
      sys.exit(2)
   for opt, arg in opts:
      if opt == '-h':
         print ('graphit -i <Linuxkit yml> -o <Diagram SVG>')
         sys.exit()
      elif opt in ("-i", "--ifile"):
         inputfile = arg
      elif opt in ("-o", "--ofile"):
         outputfile = arg
   print ('Reading Linuxkit configuration file:',inputfile)
   print ('Diagram will be at:',outputfile+'.svg')

   try:
       with open(inputfile, 'r') as stream:
            try:
                linuxkityaml = yaml.load(stream)
            except yaml.YAMLError as exc:
                print("Failed to read YAML from:",inputfile)
                print("  >", exc)
   except IOError as e:
        print("Input file could not be read:",inputfile)
        print("  >", e)
   stream.close()

   # Pass our linixkit yaml on to be parsed
   parselkyaml(linuxkityaml)

   # We can build a graph for kernel and init without pulling docker LABEL matadata
   # Because there arent any mounts/binds for those components (or a LABEL for that point).
   graph = buildkernelgraph()
   graph = addinitgraph(graph)

   # More complex images w/metadata labels for onboot and services
   graph = addonbootgraph(graph)
   graph = addservicesgraph(graph)

   # Make our graph prettier.
   styles = {
     'nodes': {
         'fontname': 'Helvetica',
         'shape': 'rectangle'
     },
     'edges': {
         'arrowhead': 'open',
         'fontname': 'Helvetica',
         'fontsize': '12'
     }
   }

   graph = apply_styles(graph,styles)
   #graph.render('img/test-g3')

   #Output our graph.
   graphoutput(graph,outputfile)

def parselkyaml(linuxkityaml):

   global kernels
   global init
   global onboot
   global services
   global files

   # Kernels is pretty simple. Making it nested so it matches the others.
   # Name will always be kernel, in others it will be the onboot/service item names.
   kernels['kernel'] = {}
   kernels['kernel']['image'] = linuxkityaml['kernel']['image']
   #print(kernels)

   # Multiple init items, each one is just the image name and version.
   # We have no nice "name" here either, so value and key are the same.
   for init_items in linuxkityaml['init']:
       init[init_items] = init_items
   #print(init)

   # Now for the real stuff. onboot we have a name and an image.
   # The returned onboot_items object from yml is handily a dict;
   # so have nested the whole thing under each items 'name'.
   # Image for sysctl would be: print(onboot[sysctl][image])
   for onboot_items in linuxkityaml['onboot']:
       onboot[onboot_items['name']] = onboot_items
       #print(onboot)
   #print(onboot['sysctl']['image'])

   # Same for services
   for services_items in linuxkityaml['services']:
       services[services_items['name']] = services_items
       #print(services)
   #print(services['kubelet']['image'])

   # Lets do files as well, as they are a source of data not covered elsewhere.
   # Indexed by path as we dont have a name.
   for files_items in linuxkityaml['files']:
       files[files_items['path']] = files_items
       #print(files)
   #print(files['/etc/kubeadm/kube-system.init/50-network.yaml'])

   # Done buildig our basic information sources.
   return

def buildkernelgraph():
   # The : between image and version breaks graph.render
   # (mistakes the version as a port onn the node) Replace with newline.
   key = kernels['kernel']['image']
   colonoscopykey = key.replace(":", "\n", 1)
   # Build a graphviz object and use the global kernels dict to plot our first item.
   graph = add_nodes(digraph(), [
      ('kernel', {'label': colonoscopykey})
   ])
   #graph.render('img/test-g1')
   return graph

def addinitgraph(gIN):
   # Graphviz object passed in. For each init item in init{}
   # add nodes and links back to rootfs node.
   graph = add_edges(
    add_nodes(gIN, [('rootfs', {'label': 'RootFS'})]),
    [(('kernel', 'rootfs'))])

   nodeslist=[]
   edgelist=[]
   for key, value in init.items():
       # The : between image and version breaks graph.render
       # (mistakes the version as a port onn the node) Replace with newline.
       colonoscopykey = key.replace(":", "\n", 1)
       nodeslist.append(colonoscopykey)
       edgelist.append((colonoscopykey,'rootfs'))
   graph = add_edges(add_nodes(graph, nodeslist),edgelist)
   #graph.render('img/test-g2')
   return graph

def addonbootgraph(gIN):
    # Graphviz object passed in. For each onboot item (Howto visualize?)
    # Lots of mounts on one line / node would be just as bad as reading the metadata
    # from the Dockerfile / image.

    # Maybe a subgraph per onboot item fanning out to a node per mount, with the line
    # FROM RootFS showing where in rootFS the mount is FROM, and the node showing what it
    # IS in the onboot container. Also maybe colour the node box for rshared/rbind.

   nodeslist=[]
   edgelist=[]

   #FOR A GIVEN IMAGE...
   for key, value in onboot.items():
       # The : between image and version breaks graph.render
       # (mistakes the version as a port onn the node) Replace with newline.
       colonoscopyimagename = value['image'].replace(":", "\n", 1)

       # Our "Primary" node will have the onboot name, image name, and version.
       nodeslist.append(((key + "\n" + colonoscopyimagename), {'color': 'red'}))

       # For links we need to query the docker image and parse the mounts.
       mobyconfig = getdockerlabel(value['image'])

       # From the config we want a simple dict of binds, mounts and details.
       # Return is in the following format: SRC {dest: dest, rshared: Boolean, rbind: Boolean }
       # Example {'/etc/resolv.conf': {'dest': '/etc/resolv.conf', 'rshared': False, 'rbind': False}}
       dictofbinds = parsemobyconfig(mobyconfig)

       print("For image:",key, "-- Binds:",dictofbinds)
       # Add to nodelist and edgelist for our new binds.
       if dictofbinds:
           # Dict has content, process binds into graphs.
           # EACH BIND FOR A GIVEN IMAGE...
           for bind, innerdict in dictofbinds.items():
              nodeslist.append((innerdict['dest'], {'label': innerdict['dest'], 'color': 'red'}))
              edgelist.append((('rootfs',innerdict['dest']), {'label': bind + "\n rshared:" + str(innerdict['rshared']) + "\n rbind:" + str(innerdict['rbind']), 'color': 'red'}))
              edgelist.append(((innerdict['dest'], key + "\n" + colonoscopyimagename), {'color': 'red'}))
       else:
           #Empty dict, Just attach the node directly FROM rootfs.
           edgelist.append((('rootfs', key + "\n" + colonoscopyimagename), {'color': 'red'}))


   # Update and return our graph
   graph = add_edges(add_nodes(gIN, nodeslist),edgelist)

   return graph

def addservicesgraph(gIN):
    # Graphviz object passed in. For each onboot item (Howto visualize?)
    # Lots of mounts on one line / node would be just as bad as reading the metadata
    # from the Dockerfile / image.

    # Maybe a subgraph per onboot item fanning out to a node per mount, with the line
    # FROM RootFS showing where in rootFS the mount is FROM, and the node showing what it
    # IS in the onboot container. Also maybe colour the node box for rshared/rbind.

   nodeslist=[]
   edgelist=[]

   #FOR A GIVEN IMAGE...
   for key, value in services.items():
       # The : between image and version breaks graph.render
       # (mistakes the version as a port onn the node) Replace with newline.
       colonoscopyimagename = value['image'].replace(":", "\n", 1)

       # Our "Primary" node will have the onboot name, image name, and version.
       nodeslist.append(((key + "\n" + colonoscopyimagename), {'color': 'blue'}))

       # For links we need to query the docker image and parse the mounts.
       mobyconfig = getdockerlabel(value['image'])

       # From the config we want a simple dict of binds, mounts and details.
       # Return is in the following format: SRC {dest: dest, rshared: Boolean, rbind: Boolean }
       # Example {'/etc/resolv.conf': {'dest': '/etc/resolv.conf', 'rshared': False, 'rbind': False}}
       dictofbinds = parsemobyconfig(mobyconfig)

       print("For image:",key, "-- Binds:",dictofbinds)
       # Add to nodelist and edgelist for our new binds.
       if dictofbinds:
           # Dict has content, process binds into graphs.
           # EACH BIND FOR A GIVEN IMAGE...
           for bind, innerdict in dictofbinds.items():
              nodeslist.append((innerdict['dest'], {'label': innerdict['dest'], 'color': 'blue'}))
              edgelist.append((('rootfs',innerdict['dest']), {'label': bind + "\n rshared:" + str(innerdict['rshared']) + "\n rbind:" + str(innerdict['rbind']), 'color': 'blue'}))
              edgelist.append(((innerdict['dest'], key + "\n" + colonoscopyimagename), {'color': 'blue'}))
       else:
           #Empty dict, Just attach the node directly FROM rootfs.
           edgelist.append((('rootfs', key + "\n" + colonoscopyimagename), {'color': 'blue'}))


   # Update and return our graph
   graph = add_edges(add_nodes(gIN, nodeslist),edgelist)

   return graph



def getdockerlabel(imagenametag):
   # Here we want to pull a docker container, read the labels, return the json object

   # I know exec out to docker is nasty as hell, but the pydocker module appears to only
   # support inspect on continers, not images.. (and it's 2AM, #FIXME)
   subprocess.getoutput("docker pull "+ imagenametag)
   mobyprojectconfig = subprocess.getoutput("docker inspect --format='{{json .Config.Labels}}' " + imagenametag)
   return mobyprojectconfig

def parsemobyconfig(mobyconfig):
    # He're we'll be passed the .Config.Labels section of docker inspect json.
    # Pick out all the binds and mounts from org.mobyproject.config and
    # Turn them into a dict or list of info.
    dictbinds = {}

    try:
       parsed_json = json.loads(mobyconfig)
       reparsed_json = json.loads(parsed_json["org.mobyproject.config"])
    except ValueError:
       print("Decoding JSON from docker inspect failed")

    try:
       binds = reparsed_json["binds"]
       mounts = reparsed_json["mounts"]

       #Awesome, a list of binds. Iter through them to following format:
       #Dict{from{too,rshared(truefalse),rbind(truefalse)}}
       for bind in binds:
          #print("Unprocessed:")
          #print(bind)
          parts = bind.split(":")
          if len(parts)>2:
              if parts[2] == "rshared,rbind":
                  dictbinds[parts[0]] = {'dest': parts[1], 'rshared': True, 'rbind': True}
              if parts[2] == "rbind,rshared":
                  dictbinds[parts[0]] = {'dest': parts[1], 'rshared': True, 'rbind': True}
              if parts[2] == "rshared":
                  dictbinds[parts[0]] = {'dest': parts[1], 'rshared': True, 'rbind': False}
              if parts[2] == "rbind":
                  dictbinds[parts[0]] = {'dest': parts[1], 'rshared': False, 'rbind': True}
          else:
              dictbinds[parts[0]] = {'dest': parts[1], 'rshared': False, 'rbind': False}
          #print("Processed:")
          #print(dictbinds)

    except KeyError:
        #print("Skipping item. No Binds or Mounts")
        pass

    #Return a dictionary of binds #TODO Add mounts.
    return dictbinds

def graphoutput(graph,outputfile):
        graph.render(outputfile)


if __name__ == "__main__":
   main(sys.argv[1:])
