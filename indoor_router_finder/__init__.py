"""
Classes/functions used in main program
"""
import copy
import math
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

    def __init__(self, graphml_string: str, stair_weight=100):
        self.graphml = graphml_string
        nx = networkx.parse_graphml(self.graphml)
        node_pos = {}

        for key, d in nx.nodes(data=True):
            node_pos[key] = {'x': float(d['x']), 'y': float(d['y'])}
            self.labels_to_keys[d['label']] = key
            self.keys_to_labels[key] = d['label']
        for edge in nx.edges():
            s_id = edge[0]
            t_id = edge[1]
            source = node_pos[s_id]
            target = node_pos[t_id]
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

    def calc_paths(self, controls, max_routes: int):
        for i, (curr_c, next_c) in enumerate(zip(controls, controls[1:])):
            print(f'K{i} to K{i + 1}:')
            print(f'{curr_c} to {next_c}:')
            try:
                path = list(islice(
                    networkx.algorithms.shortest_simple_paths(
                        self.nx, self.labels_to_keys.get(curr_c),
                        self.labels_to_keys.get(next_c),
                        weight='weight'),
                    max_routes)
                )
                best_score = 2 ** 32
                p: list
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
            except NetworkXNoPath as e:
                print('No path found. Hm...', e)
