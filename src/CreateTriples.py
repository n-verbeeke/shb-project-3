'''
Code retrieved from https://github.com/alishiba14/WorldKG-Knowledge-Graph/blob/main/CreateTriples.py

Install the Python Requirements pip install -r requirements.txt
Download the specific OpenStreetMap snapshot, e.g., from https://download.geofabrik.de/. We recommend using the osm.pbf format.
Run the CreateTriples.py: python3 CreateTriples.py /path-to-pbf-file /path-to-the-ttl-file-to-save-triples

''' 

import osmium
import numpy as np
import pandas as pd
import re
import sys
import urllib
import time
from rdflib import Graph, Namespace, URIRef, BNode, Literal
from rdflib.namespace import RDF, FOAF, XSD

from shapely.geometry import Point, Polygon

# Create a shapely Polygon of Trento:
# Read coordinates from the text file containing polygon coordinates
file_path = "./trento_polygon.txt" # Polygon Values retrieved from https://polygons.openstreetmap.fr/index.py?id=46663
with open(file_path, 'r') as file:
    coordinates = [line.split() for line in file]

# Extract x and y values from the coordinates
x_vals = [float(coord[0]) for coord in coordinates]
y_vals = [float(coord[1]) for coord in coordinates]

# Create Shapely Polygon
polygon_to_filter = Polygon(zip(x_vals, y_vals))

start = time.time()
class osm2rdf_handler(osmium.SimpleHandler):
    def __init__(self):
        osmium.SimpleHandler.__init__(self)    
        self.counts=0
        self.g = Graph()
        self.graph = self.g
        self.wd = Namespace("http://www.wikidata.org/wiki/")
        self.g.bind("wd", self.wd)
        self.wdt = Namespace("http://www.wikidata.org/prop/direct/")
        self.g.bind("wdt", self.wdt)
        self.wkg = Namespace("http://www.worldkg.org/resource/")
        self.g.bind("wkg", self.wkg)
        self.wkgs = Namespace("http://www.worldkg.org/schema/")
        self.g.bind("wkgs", self.wkgs)
        self.geo = Namespace("http://www.opengis.net/ont/geosparql#")
        self.g.bind("geo", self.geo)
        self.rdfs = Namespace('http://www.w3.org/2000/01/rdf-schema#')
        self.g.bind("rdfs", self.rdfs)
        self.rdf = Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
        self.g.bind('rdf',self.rdf)
        self.ogc=Namespace("http://www.opengis.net/rdf#")
        self.g.bind('ogc',self.ogc)
        self.sf = Namespace("http://www.opengis.net/ont/sf#")
        self.g.bind('sf', self.sf)
        self.osmn = Namespace("https://www.openstreetmap.org/node/")
        self.g.bind("osmn", self.osmn)
        self.supersub = pd.read_csv('OSM_Ontology_map_features.csv', sep='\t', encoding='utf-8')
        self.key_list = pd.read_csv('Key_List.csv', sep='\t', encoding='utf-8')
        self.key_list = list(self.key_list['key'])
        self.supersub = self.supersub.drop_duplicates()
        
        self.dict_class = self.supersub.groupby('key')['value'].apply(list).reset_index(name='subclasses').set_index('key').to_dict()['subclasses']
    
    def to_camel_case_class(self, word):
        word = word.replace(':','_')
        return ''.join(x.capitalize() or '_' for x in word.split('_'))
    
    def to_camel_case_classAppend(self, key, val):
        return self.supersub.loc[(self.supersub['value'] == val) & (self.supersub['key'] == key)]['appendedClass'].values[0]
    
    def to_camel_case_key(self, input_str):
        input_str = input_str.replace(':','_')
        words = input_str.split('_')
        return words[0] + "".join(x.title() for x in words[1:])
    
    def printTriple(self, s, p, o):
        if p in self.dict_class: 
            if o in self.dict_class[p]:
                rel = URIRef('http://www.worldkg.org/resource/' + s)
                instanceOf = URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
                res = URIRef('http://www.worldkg.org/schema/' + self.to_camel_case_classAppend(p,o))
                self.g.add((rel, instanceOf , res))
            if o == 'Yes':
                rel = URIRef('http://www.worldkg.org/resource/' + s)
                instanceOf = URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
                res = URIRef('http://www.worldkg.org/schema/' + self.to_camel_case_class(p))
                self.g.add((rel, instanceOf , res))
        else:
            if p=='Point':
                sub = URIRef('http://www.worldkg.org/resource/' + s)
                geoprop = URIRef('http://www.worldkg.org/schema/spatialObject')
                geoobj = URIRef('http://www.worldkg.org/resource/geo' + s)
                prop = URIRef('http://www.opengis.net/ont/sf#Point')
                typ = URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
                self.g.add((sub, geoprop, geoobj))
                self.g.add((geoobj, typ, prop))
                self.g.add((geoobj, self.geo["asWKT"], Literal(o, datatype=self.geo.wktLiteral)))
            elif p == 'osmLink':
                sub = URIRef('http://www.worldkg.org/resource/' + s)
                prop = URIRef('http://www.worldkg.org/schema/osmLink')
                obj = URIRef('https://www.openstreetmap.org/node/'+o)
                self.g.add((sub,prop,obj))
            elif p == 'osmLinkWay':
                sub = URIRef('http://www.worldkg.org/resource/' + s)
                prop = URIRef('http://www.worldkg.org/schema/osmLink')
                obj = URIRef('https://www.openstreetmap.org/way/'+o)
                self.g.add((sub,prop,obj))
            elif p == 'name':
                sub = URIRef('http://www.worldkg.org/resource/' + s)
                prop = URIRef('http://www.w3.org/2000/01/rdf-schema#label')
                self.g.add((sub, prop, Literal(o)))
            elif p == 'wikidata':
                sub = URIRef('http://www.worldkg.org/resource/' + s)
                prop = URIRef("http://www.worldkg.org/schema/" + p)
                if o.startswith('Q'):
                    obj = URIRef('http://www.wikidata.org/wiki/' + o)
                else:
                    obj = Literal(o)
                self.g.add((sub, prop, obj))
            elif p == 'wikipedia':
                sub = URIRef('http://www.worldkg.org/resource/' + s)
                prop = URIRef("http://www.worldkg.org/schema/wikipedia" )
                try:
                    country = o.split(':')[0]
                    ids = o.split(':')[1]
                    #ids = urllib.parse.quote(o.split(':')[1])
                except IndexError:
                    country = ''
                    #ids = urllib.parse.quote(o)
                    ids = o
                url = country+'.wikipedia.org/wiki/'+country+':'+ids
                url = 'https://'+urllib.parse.quote(url)
                obj = URIRef(url)
                self.g.add((sub, prop, obj))
            else:
                if p in self.key_list:
                    sub = URIRef('http://www.worldkg.org/resource/' + s)
                    prop = URIRef("http://www.worldkg.org/schema/" + self.to_camel_case_key(p))
                    self.g.add((sub, prop, Literal(o)))
        
    def __close__(self):
        print(str(self.counts))

    def way(self, w):
        if len(w.tags)>1 and len(w.nodes)>1:
            if "amenity" not in w.tags:
                return

            # Problem: OSM Way does not have coordinates (lat,lng)
            # A simple workaround is to obtain the lat,lng of the first node of the way

            lat = str(w.nodes[0].location.lat)
            lon = str(w.nodes[0].location.lon)
            
            w_point = Point(lon, lat)

            # Check if the first node of the way is located within Trento polygon
            if polygon_to_filter.contains(w_point):     
                id = str(w.id)
                point = 'Point('+str(lon)+' '+str(lat)+')'
                self.printTriple(id, "Point", point)
                self.printTriple(id,"osmLinkWay",id)


                for k,v in w.tags:
                    val = str(v)
                    val=val.replace("\\", "\\\\")
                    val=val.replace('"', '\\"')
                    val=val.replace('\n', " ")
                    k = k.replace(" ", "")
                    self.printTriple(id, k, val)


    def node(self, n):
        if len(n.tags)>1:
            if "amenity" not in n.tags:
                return
    
            lat = str(n.location.lat)
            lon = str(n.location.lon)

            n_point = Point(lon, lat)

            # Check if the node is located within Trento polygon
            if polygon_to_filter.contains(n_point):
                id = str(n.id)

                point = 'Point('+str(n.location.lon)+' '+str(n.location.lat)+')'

                self.printTriple(id, "Point", point)
                self.printTriple(id,"osmLink",id)


                for k,v in n.tags:

                    val = str(v)

                    val=val.replace("\\", "\\\\")
                    val=val.replace('"', '\\"')
                    val=val.replace('\n', " ")

                    k = k.replace(" ", "")

                    self.printTriple(id, k, val)


h = osm2rdf_handler()
h.apply_file(sys.argv[1],locations=True)
h.graph.serialize(sys.argv[2],format="turtle", encoding = "utf-8" )
end = time.time()
print(end - start)


'''
# License
MIT License

Copyright (c) 2021 Alishiba Dsouza

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

'''