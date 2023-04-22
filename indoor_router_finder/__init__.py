"""
Classes/functions used in main program
"""
import copy

from lxml import etree


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
