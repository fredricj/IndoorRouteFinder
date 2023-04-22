"""
Classes/functions used in main program
"""
from PIL import Image, ImageDraw
import copy
import math
import os
from itertools import islice

import networkx
from lxml import etree
from networkx import NetworkXNoPath, path_weight


def read_and_preprocess_graphml(input_graphml_file: str) -> str:
    """
    Reads a graphml generated in yEd and returns an adjusted
    graph suitable for path finding. Graphml only supports
    directed edges, but we usually allow running in both
    directions.

    :param input_graphml_file:
    :return str:
    """
    e = etree.parse(input_graphml_file)
    root = e.getroot()
    graph = root.find('graph', namespaces=root.nsmap)
    for edge in graph.findall('edge', namespaces=root.nsmap):
        for arrow in edge.iterfind('.//y:Arrows', namespaces=root.nsmap):
            if arrow.get('target') == 'none':
                # If not targeted then we assume the edge is supposed to be
                # undirected so create an edge in the other direction
                new_edge = copy.deepcopy(edge)
                source = new_edge.get('source')
                target = new_edge.get('target')
                new_edge.set('source', target)
                new_edge.set('target', source)
                new_edge.set('id', new_edge.get('id') + 'rev')
                graph.append(new_edge)
                break
    return etree.tostring(e, encoding='unicode')


def preprocess_controls(control_string: str) -> list:
    """
    Splits the input control string into a list

    :param control_string:
    :return:
    """
    return control_string.split(',')


def get_stair_count_in_path(path_labels):
    stairs = list(filter(lambda f: f[0].isalpha() and f[0:2].lower() != 'ko', path_labels))
    return int(len(stairs) / 2)


class RouteCalculator:
    labels_to_keys: dict = {}
    keys_to_labels: dict = {}
    nx = None
    graphml: str = None
    node_pos = None

    def __init__(self, graphml_string: str, stair_weight=100):
        self.graphml = graphml_string
        nx = networkx.parse_graphml(self.graphml)
        self.node_pos = {}

        for key, d in nx.nodes(data=True):
            self.node_pos[key] = {'x': float(d['x']), 'y': float(d['y'])}
            self.labels_to_keys[d['label']] = key
            self.keys_to_labels[key] = d['label']
        for edge in nx.edges():
            s_id = edge[0]
            t_id = edge[1]
            source = self.node_pos[s_id]
            target = self.node_pos[t_id]
            s_label = self.keys_to_labels[s_id].lower()
            t_label = self.keys_to_labels[t_id].lower()
            # Stair nodes between floors are named [a-z][0-9]-[1-2],
            # where the letter names the stair well, the first number
            # denotes the lower floor in the edge so 1 means stair
            # between floor 1 and 2 and the second number is to have
            # a unique id for nodes within this pair
            # FIXME: Only supports floors 1-9
            if s_label[0].isalpha() and t_label[0].isalpha() \
                    and s_label[0:1] == t_label[0:1] \
                    and s_label[0:1] != 'ko':
                # Stair
                weight = stair_weight
            else:
                s_x = source.get('x')
                s_y = source.get('y')
                t_x = target.get('x')
                t_y = target.get('y')
                weight = math.sqrt((s_x - t_x) ** 2 + (s_y - t_y) ** 2)
            nx[edge[0]][edge[1]]['weight'] = weight
        self.nx = nx

    def calc_paths(self, controls, max_routes: int, background_image: str, output_directory: str):
        for i, (curr_c, next_c) in enumerate(zip(controls, controls[1:])):
            print(f'K{i} to K{i + 1} ({curr_c} to {next_c}):')
            try:
                path = list(islice(
                    networkx.algorithms.shortest_simple_paths(
                        self.nx, self.labels_to_keys.get(curr_c),
                        self.labels_to_keys.get(next_c),
                        weight='weight'),
                    max_routes)
                )
                best_score = 2 ** 32
                for idx, p in enumerate(path):
                    path_labels = [self.keys_to_labels.get(key) for key in p]
                    w = round(path_weight(self.nx, p, weight="weight"))
                    if idx == 0:
                        best_score = w
                    if w > best_score * 3:
                        break

                    path_str = ' -> '.join(path_labels)
                    stair_count = get_stair_count_in_path(path_labels)
                    print(f'Cost: {w}, {stair_count} stairs, Path: {path_str}')
                    try:
                        os.mkdir(output_directory)
                    except FileExistsError:
                        pass
                    base_filename = f'K{i}_to_K{i + 1}_{idx}'
                    output_file = os.path.join(output_directory, base_filename+'.graphml')
                    self.create_output_graphml_file(p, output_file)
                    self.create_route_image(os.path.join(output_directory, base_filename + '.png'), background_image, p)
            except NetworkXNoPath as e:
                print('No path found. Hm...', e)

    def create_output_graphml_file(self, path: list, output_file):
        root = etree.fromstring(self.graphml)
        graph = root.find('graph', namespaces=root.nsmap)
        edges = {}
        for curr_c, next_c in zip(path, path[1:]):
            if curr_c not in edges:
                edges[curr_c] = {}
            edges[curr_c][next_c] = 1
            curr_label = self.keys_to_labels.get(curr_c)
            next_label = self.keys_to_labels.get(next_c)
            for el in graph.iterfind(f'.//edge[@source="{curr_c}"]', namespaces=root.nsmap):
                if el.get('target') == next_c:
                    if (curr_label.endswith('-1') or curr_label.endswith('-2')) and (
                            next_label.endswith('-1') or next_label.endswith('-2')):
                        # Remove the edges for the stairs
                        graph.remove(el)
                        break
                    for line in el.iterfind('.//y:LineStyle', namespaces=root.nsmap):
                        line.set('color', '#00FF00')
                        line.set('width', '16')
                    for line in el.iterfind('.//y:Arrows', namespaces=root.nsmap):
                        line.set('target', 'standard')
        # Removes unused edges
        for el in graph.iterfind(f'.//edge', namespaces=root.nsmap):
            try:
                edges[el.get('source')][el.get('target')]
            except KeyError:
                graph.remove(el)
        # Remove unused nodes and hide the remaining nodes
        for el in graph.iterfind('.//node', namespaces=root.nsmap):
            i = el.get('id')
            try:
                path.index(i)
                for line in el.iterfind('.//y:Geometry', namespaces=root.nsmap):
                    org_height = float(line.get('height'))
                    org_width = float(line.get('width'))
                    line.set('height', '0')
                    line.set('width', '0')
                    line.set('x', str(float(line.get('x')) + org_width / 2.0))
                    line.set('y', str(float(line.get('y')) + org_height / 2.0))
            except ValueError:
                graph.remove(el)
        root.getroottree().write(output_file, xml_declaration=True, encoding='UTF-8')

    def create_route_image(self, output_file: str, image: str, path_nodes: list):
        img = Image.open(image)
        imgd = ImageDraw.Draw(img)
        line = []
        lines = []
        for p in path_nodes:
            s = self.node_pos.get(p)
            line.append((s['x'], s['y']))
            if '-' in self.keys_to_labels.get(p) and len(line) > 1:
                lines.append(line)
                line = []
        lines.append(line)
        for line in lines:
            if len(line):
                imgd.line(line, fill='red', width=20, joint='curve')
        img.save(output_file, 'PNG')

