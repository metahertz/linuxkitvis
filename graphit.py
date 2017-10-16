#!/usr/bin/env python3

import sys, getopt
import graphviz as gv
import yaml
import functools

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
   print ('Reading Linuxkit configuration file: ', inputfile)
   print ('Diagram will be at : ', outputfile)

   try:
       with open(inputfile, 'r') as stream:
            try:
                linuxkityaml = yaml.load(stream)
            except yaml.YAMLError as exc:
                print("Failed to read YAML from: ", inputfile)
                print("  >", exc)
   except IOError as e:
        print("Input file could not be read: ", inputfile)
        print("  >", e)
   stream.close()

   # Pass our linixkit yaml on to be parsed
   parselkyaml(linuxkityaml)

   # We can build a graph for kernel and init without pulling docker LABEL matadata
   # Because there arent any mounts/binds for those components (or a LABEL for that point).
   graph = buildkernelgraph()
   graph = addinitgraph(graph)

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
   #so have nested the whole thing under each items 'name'.
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
   print(nodeslist)
   print(edgelist)
   graph = add_edges(add_nodes(graph, nodeslist),edgelist)
   #graph.render('img/test-g2')
   return graph

def getdockerlabel():
   # Here we want to pull a docker container, read the labels, return the json object
   #docker inspect --format='{{json .Config.Labels}}'
   return

if __name__ == "__main__":
   main(sys.argv[1:])
